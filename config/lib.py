import json
import os

from interface.logger import Logger

DEFUALT_CONFIG = {
    "TOKEN": "ENTER-TOKEN-HERE",
    "GUILD_ID": 1234567890123456789
}

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'data', 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    else:
        with open(config_path, 'w') as f:
            json.dump(DEFUALT_CONFIG, f, indent=4)
        Logger.info("Configuration -", f"Default config created at {config_path}. Please update it with your settings.")
        return DEFUALT_CONFIG
    
def get_config_value(key):
    config = load_config()
    return config.get(key)

TOKEN = get_config_value("TOKEN")
GUILD_ID = get_config_value("GUILD_ID")