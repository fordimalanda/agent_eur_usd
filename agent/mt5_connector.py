import MetaTrader5 as mt5
import pandas as pd
import logging
import os
from dotenv import load_dotenv
from datetime import datetime

# Configuration des logs pour voir ce que fait le bot en temps réel
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Chargement des variables d'environnement (.env)
load_dotenv()

class MT5Connector:
    def __init__(self):
        self.login = int(os.getenv("MT5_LOGIN"))
        self.password = os.getenv("MT5_PASSWORD")
        self.server = os.getenv("MT5_SERVER")
        self.symbol = "EURUSD"
        self.is_connected = False

    def connect(self):
        """Initialise la connexion avec le terminal MetaTrader 5."""
        if not mt5.initialize(login=self.login, password=self.password, server=self.server):
            logger.error(f"Échec de la connexion à MT5. Erreur : {mt5.last_error()}")
            return False
        
        self.is_connected = True
        logger.info(f"Connecté à MT5. Compte : {self.login} sur {self.server}")
        return True

    def disconnect(self):
        """Ferme proprement la connexion."""
        mt5.shutdown()
        self.is_connected = False
        logger.info("Déconnecté de MT5.")

    def get_account_info(self):
        """Récupère les informations du compte (solde, équité, marge libre)."""
        info = mt5.account_info()
        if info is None:
            logger.error("Impossible de récupérer les infos du compte.")
            return None
        return info._asdict()

    def get_candles(self, timeframe=mt5.TIMEFRAME_H1, count=100):
        """Récupère les dernières bougies pour l'analyse."""
        rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, count)
        if rates is None:
            logger.error(f"Impossible de récupérer les bougies pour {self.symbol}.")
            return None
        
        # Conversion en DataFrame Pandas pour faciliter les calculs (RSI, etc.)
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def get_open_positions(self):
        """Vérifie si le bot a déjà une position ouverte sur l'EUR/USD."""
        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None:
            return []
        return positions

    def execute_order(self, action, lot_size=0.01, sl_pips=50, tp_pips=100):
        """
        Ouvre un ordre Buy ou Sell avec Stop Loss et Take Profit.
        action : "BUY" ou "SELL"
        """
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            logger.error(f"Symbole {self.symbol} introuvable.")
            return False

        # S'assurer que le symbole est visible dans la Market Watch
        if not symbol_info.visible:
            if not mt5.symbol_select(self.symbol, True):
                logger.error(f"Impossible d'ajouter {self.symbol} à la Market Watch.")
                return False

        point = symbol_info.point
        price = mt5.symbol_info_tick(self.symbol)

        # Calcul des prix d'entrée, SL et TP
        # Note: 1 pip sur EURUSD (5 décimales) = 10 points MT5
        if action == "BUY":
            order_type = mt5.ORDER_TYPE_BUY
            price_current = price.ask
            sl = price_current - (sl_pips * 10 * point)
            tp = price_current + (tp_pips * 10 * point)
        elif action == "SELL":
            order_type = mt5.ORDER_TYPE_SELL
            price_current = price.bid
            sl = price_current + (sl_pips * 10 * point)
            tp = price_current - (tp_pips * 10 * point)
        else:
            logger.error("Action invalide. Utilisez 'BUY' ou 'SELL'.")
            return False

        # Création de la requête d'ordre
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": float(lot_size),
            "type": order_type,
            "price": price_current,
            "sl": float(sl),
            "tp": float(tp),
            "deviation": 20, # Tolérance de slippage
            "magic": 202411, # Identifiant unique pour ton bot
            "comment": "Agent_EUR_USD",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC, # Force IOC (souvent requis)
        }

        # Envoi de l'ordre
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Échec de l'ordre {action}. Code: {result.retcode}, Commentaire: {result.comment}")
            return False
        
        logger.info(f"Ordre {action} exécuté avec succès ! Ticket: {result.order}, Prix: {price_current}")
        return result.order

    def close_position(self, ticket):
        """Ferme une position spécifique en fonction de son ticket."""
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            logger.error(f"Position {ticket} introuvable.")
            return False
        
        position = positions[0]
        # Pour fermer un Buy, on fait un Sell au prix Bid, et inversement
        order_type = mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(self.symbol).bid if order_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(self.symbol).ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": position.volume,
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 202411,
            "comment": "Close_by_Agent",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Échec de la fermeture de la position {ticket}. Code: {result.retcode}")
            return False
        
        logger.info(f"Position {ticket} fermée avec succès.")
        return True

# --- Bloc de test (s'exécute uniquement si on lance ce fichier directement) ---
if __name__ == "__main__":
    bot = MT5Connector()
    if bot.connect():
        # 1. Test récupération des données
        df = bot.get_candles(count=5)
        print("\n--- 5 Dernières bougies H1 ---")
        print(df[['time', 'open', 'high', 'low', 'close']])
        
        # 2. Test récupération du compte
        account = bot.get_account_info()
        print(f"\n--- Solde du compte : {account['balance']} {account['currency']} ---")
        
        # 3. Test des positions ouvertes
        positions = bot.get_open_positions()
        print(f"\nPositions ouvertes sur EURUSD : {len(positions)}")
        
        bot.disconnect()