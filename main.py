import json
import logging
import sys
from Server import Server

if __name__ == "__main__":
    config = None
    
    logger = logging.getLogger("Server")
    logger.setLevel(logging.DEBUG)
    
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    
    file_handler = logging.FileHandler("server.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    try:
        with open("config.json", "r", encoding="utf-8") as config_file:
            config = json.load(config_file)
    except FileNotFoundError:
        logger.error("No config.json file provided")
        exit(1)
    
    server = Server(config, logger)
    try:
        server.run()
    except Exception as exc:
        logger.error(exc)
        server.close()
        