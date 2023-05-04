import os
from dotenv import dotenv_values

# Load .env
env = dotenv_values('.env')

# Read variables with priority: .env > environment variables > default values
API_ID = env.get('API_ID') or os.environ.get('API_ID')
API_KEY = env.get('API_KEY') or os.environ.get('API_KEY')
BOT_TOKEN = env.get('BOT_TOKEN') or os.environ.get('BOT_TOKEN')
ALLOWED_USER_IDS = env.get('ALLOWED_USER_IDS') or os.environ.get('ALLOWED_USER_IDS')
ALLOWED_USER_IDS = [ int(uid.strip()) for uid in ALLOWED_USER_IDS.split(",") ]
COOKIE_FILE = env.get('COOKIE_FILE') or os.environ.get('COOKIE_FILE') or "./cookie.json"

NOT_ALLOW_INFO = env.get('NOT_ALLOW_INFO') or os.environ.get('NOT_ALLOW_INFO') or ""
BOT_NAME = env.get('BOT_NAME') or os.environ.get('BOT_NAME') or "PyroEdgeGptBot"
SUGGEST_MODE = env.get('SUGGEST_MODE') or os.environ.get('SUGGEST_MODE') or "callbackquery"
DEFAULT_CONVERSATION_STYLE_TYPE = env.get('DEFAULT_CONVERSATION_STYLE_TYPE') or os.environ.get('DEFAULT_CONVERSATION_STYLE_TYPE') or "creative"
RESPONSE_TYPE = env.get('RESPONSE_TYPE') or os.environ.get('RESPONSE_TYPE') or "normal"
STREAM_INTERVAL = env.get('STREAM_INTERVAL') or os.environ.get('STREAM_INTERVAL') or 5
STREAM_INTERVAL = int(STREAM_INTERVAL)
LOG_LEVEL = env.get('LOG_LEVEL') or os.environ.get('LOG_LEVEL') or "INFO"
LOG_TIMEZONE = env.get('LOG_TIMEZONE') or os.environ.get('LOG_TIMEZONE') or "Asia/Shanghai"

