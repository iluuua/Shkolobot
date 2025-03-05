import logging, os
from dotenv import load_dotenv
from pathlib import Path

path = Path('config/.env')
load_dotenv(path)

logging.basicConfig(
    level=logging.INFO,
    filename='config/logs.log',
    filemode='a',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

configs = {
    "BOT_TOKEN" : os.getenv("BOT_TOKEN"),
    "ADMIN_IDS" : [int(x) for x in os.getenv("ADMIN_IDS").split(',')]
}