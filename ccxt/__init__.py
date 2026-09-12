import sys
import os

# Evitar importación circular removiendo temporalmente la ruta local
current_dir = os.path.dirname(__file__)
if current_dir in sys.path:
    sys.path.remove(current_dir)

import ccxt as _real_ccxt

if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Re-exportar todo desde la librería real de CCXT
from ccxt import *

# Sobrescribir la clase binance para asegurar conectividad estable en la nube
class binance(_real_ccxt.binance):
    def __init__(self, config=None):
        if config is None:
            config = {}
        config.setdefault('enableRateLimit', True)
        config.setdefault('options', {'defaultType': 'future'})
        super().__init__(config)
