import time
import logging
from agent.mt5_connector import MT5Connector

# Configuration des logs pour la console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Démarrage de l'agent EUR/USD...")
    
    # Initialisation du connecteur
    bot = MT5Connector()
    
    # Tentative de connexion
    if not bot.connect():
        logger.error("Impossible de démarrer l'agent sans connexion à MT5. Arrêt.")
        return

    try:
        # --- BLOC DE TEST ---
        logger.info("--- Test de récupération des données ---")
        
        # 1. Test récupération des bougies
        df = bot.get_candles(count=5)
        if df is not None:
            print("\n5 dernières bougies H1 :")
            print(df[['time', 'open', 'high', 'low', 'close']])
        
        # 2. Test récupération du compte
        account = bot.get_account_info()
        if account:
            print(f"\nSolde du compte : {account['balance']} {account['currency']}")
        
        # 3. Test des positions ouvertes
        positions = bot.get_open_positions()
        print(f"\nPositions ouvertes sur EURUSD : {len(positions)}")
        
        logger.info("--- Fin du test. L'agent passe en mode veille. ---")
        
        # Boucle infinie pour garder le conteneur en vie
        while True:
            time.sleep(60) # Attend 60 secondes
            # Plus tard, c'est ici que nous mettrons la logique de trading
            logger.info("L'agent fait sa ronde... (analyse du marché)")

    except KeyboardInterrupt:
        logger.info("Arrêt manuel demandé.")
    finally:
        bot.disconnect()
        logger.info("Agent arrêté proprement.")

if __name__ == "__main__":
    main()