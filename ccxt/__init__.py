from ccxt import *
import ccxt as _ccxt

# Interceptar la clase binance para asegurar compatibilidad en la nube
class binance(_ccxt.binance):
    def __init__(self, config=None):
        if config is None:
            config = {}
        config.setdefault('enableRateLimit', True)
        config.setdefault('options', {'defaultType': 'future'})
        super().__init__(config)
