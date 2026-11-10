# agent/mt5_connector.py
import pandas as pd
import logging
import os
from dotenv import load_dotenv
# On importe la version "bridge" de MetaTrader5
from mt5linux import MetaTrader5 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

class MT5Connector:
    def __init__(self):
        # Le nom d'hôte est défini dans docker-compose (mt5-terminal)
        # Si on tourne en dehors de Docker, on peut utiliser 'localhost'
        self.host = os.getenv("MT5_HOST", "localhost")
        self.port = int(os.getenv("MT5_PORT", 8001))
        self.symbol = "EURUSD"
        self.mt5 = None

    def connect(self):
        """Initialise la connexion avec le serveur MT5 via mt5linux."""
        try:
            logger.info(f"Tentative de connexion à MT5 sur {self.host}:{self.port}...")
            
            # LA MODIFICATION EST ICI : on ajoute engine='remote'
            self.mt5 = MetaTrader5(host=self.host, port=self.port, engine='remote')
            
            # Initialisation de la connexion
            if not self.mt5.initialize():
                logger.error(f"Échec de l'initialisation. Erreur : {self.mt5.last_error()}")
                return False
            
            logger.info("Connecté avec succès à l'API MT5.")
            return True
        except Exception as e:
            logger.error(f"Exception lors de la connexion à MT5 : {e}")
            return False

    def disconnect(self):
        """Ferme proprement la connexion."""
        if self.mt5:
            self.mt5.shutdown()
            logger.info("Déconnecté de l'API MT5.")

    def get_account_info(self):
        """Récupère les informations du compte."""
        if not self.mt5: return None
        info = self.mt5.account_info()
        if info is None:
            logger.error("Impossible de récupérer les infos du compte.")
            return None
        return info._asdict()

    def get_candles(self, timeframe=16385, count=100): # 16385 = mt5.TIMEFRAME_H1
        """Récupère les dernières bougies pour l'analyse."""
        if not self.mt5: return None
        # Note: Les constantes de timeframe sont disponibles via self.mt5.TIMEFRAME_H1
        rates = self.mt5.copy_rates_from_pos(self.symbol, timeframe, 0, count)
        if rates is None:
            logger.error(f"Impossible de récupérer les bougies pour {self.symbol}.")
            return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def get_open_positions(self):
        """Vérifie si le bot a déjà une position ouverte sur l'EUR/USD."""
        if not self.mt5: return []
        positions = self.mt5.positions_get(symbol=self.symbol)
        if positions is None:
            return []
        return positions

    def execute_order(self, action, lot_size=0.01, sl_pips=50, tp_pips=100):
        """
        Ouvre un ordre Buy ou Sell avec Stop Loss et Take Profit.
        action : "BUY" ou "SELL"
        """
        if not self.mt5: return False
        
        symbol_info = self.mt5.symbol_info(self.symbol)
        if symbol_info is None:
            logger.error(f"Symbole {self.symbol} introuvable.")
            return False

        if not symbol_info.visible:
            if not self.mt5.symbol_select(self.symbol, True):
                logger.error(f"Impossible d'ajouter {self.symbol} à la Market Watch.")
                return False

        point = symbol_info.point
        price = self.mt5.symbol_info_tick(self.symbol)

        # Le reste de la logique est identique
        if action == "BUY":
            order_type = self.mt5.ORDER_TYPE_BUY
            price_current = price.ask
            sl = price_current - (sl_pips * 10 * point)
            tp = price_current + (tp_pips * 10 * point)
        elif action == "SELL":
            order_type = self.mt5.ORDER_TYPE_SELL
            price_current = price.bid
            sl = price_current + (sl_pips * 10 * point)
            tp = price_current - (tp_pips * 10 * point)
        else:
            logger.error("Action invalide. Utilisez 'BUY' ou 'SELL'.")
            return False

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": float(lot_size),
            "type": order_type,
            "price": price_current,
            "sl": float(sl),
            "tp": float(tp),
            "deviation": 20,
            "magic": 202411,
            "comment": "Agent_EUR_USD",
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self.mt5.ORDER_FILLING_IOC,
        }

        result = self.mt5.order_send(request)
        
        if result.retcode != self.mt5.TRADE_RETCODE_DONE:
            logger.error(f"Échec de l'ordre {action}. Code: {result.retcode}, Commentaire: {result.comment}")
            return False
        
        logger.info(f"Ordre {action} exécuté ! Ticket: {result.order}, Prix: {price_current}")
        return result.order

    def close_position(self, ticket):
        """Ferme une position spécifique en fonction de son ticket."""
        if not self.mt5: return False
        positions = self.mt5.positions_get(ticket=ticket)
        if not positions:
            logger.error(f"Position {ticket} introuvable.")
            return False
        
        position = positions[0]
        order_type = self.mt5.ORDER_TYPE_SELL if position.type == self.mt5.POSITION_TYPE_BUY else self.mt5.ORDER_TYPE_BUY
        price = self.mt5.symbol_info_tick(self.symbol).bid if order_type == self.mt5.ORDER_TYPE_SELL else self.mt5.symbol_info_tick(self.symbol).ask

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": position.volume,
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 202411,
            "comment": "Close_by_Agent",
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self.mt5.ORDER_FILLING_IOC,
        }

        result = self.mt5.order_send(request)
        if result.retcode != self.mt5.TRADE_RETCODE_DONE:
            logger.error(f"Échec de la fermeture de la position {ticket}. Code: {result.retcode}")
            return False
        
        logger.info(f"Position {ticket} fermée avec succès.")
        return True

# --- Bloc de test ---
if __name__ == "__main__":
    bot = MT5Connector()
    if bot.connect():
        df = bot.get_candles(count=5)
        print("\n--- 5 Dernières bougies H1 ---")
        print(df[['time', 'open', 'high', 'low', 'close']])
        
        account = bot.get_account_info()
        print(f"\n--- Solde du compte : {account['balance']} {account['currency']} ---")
        
        positions = bot.get_open_positions()
        print(f"\nPositions ouvertes sur EURUSD : {len(positions)}")
        
        bot.disconnect()