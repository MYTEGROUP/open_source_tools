import os
from dotenv import load_dotenv
from helpers.Manage_Json_files import JSONManager

# Load environment variables from the .env file
load_dotenv()

# Initialize JSONManager to access storage and static directories
storage_dir = JSONManager.get_storage_dir()
STATIC_DIR = JSONManager.get_static_dir()

# Paths to the config files
LOG_FILE = os.getenv('LOG_FILE', os.path.join(storage_dir, 'BackendLog.json'))
USER_INFO_FILE = os.path.join(storage_dir, 'user_info.json')

# OpenAI API Key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

LOGO_PATH = os.path.join(STATIC_DIR, 'LogoIcon.png')

# MongoDB configuration
MONGO_URI = os.getenv('MONGO_URI')
MONGO_DB = os.getenv('MONGO_DB_NAME')




