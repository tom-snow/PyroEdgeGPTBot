import os
import base64
from dotenv import dotenv_values

# Load .env
env = dotenv_values('.env')


# 配置文件不正确时的异常
class BAD_CONFIG_ERROR(Exception):
    pass


# Read variables with priority: .env > environment variables > default values
API_ID = env.get('API_ID') or os.environ.get('API_ID')
API_KEY = env.get('API_KEY') or os.environ.get('API_KEY')
BOT_TOKEN = env.get('BOT_TOKEN') or os.environ.get('BOT_TOKEN')
ALLOWED_USER_IDS = env.get('ALLOWED_USER_IDS') or os.environ.get('ALLOWED_USER_IDS') or "*"
ALLOWED_USER_IDS = [ int(uid.strip()) for uid in ALLOWED_USER_IDS.split(",") ] if ALLOWED_USER_IDS != "*" else None
SUPER_USER_IDS = env.get('SUPER_USER_IDS') or os.environ.get('SUPER_USER_IDS') or ""
SUPER_USER_IDS = [ int(uid.strip()) for uid in SUPER_USER_IDS.split(",") ] if SUPER_USER_IDS != "" else None
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


if not API_ID or not API_KEY or not BOT_TOKEN:
    raise BAD_CONFIG_ERROR(f"API_ID, API_KEY or BOT_TOKEN is not set")

if SUPER_USER_IDS is None:
    if ALLOWED_USER_IDS is None: # 允许所有人使用时必须设置管理员ID
        raise BAD_CONFIG_ERROR(f"SUPER_USER_IDS is not set")
    SUPER_USER_IDS = ALLOWED_USER_IDS # 允许部分人使用时没有设置管理员则都是管理员

if not os.path.exists(COOKIE_FILE):
    COOKIE_BASE64 = os.environ.get('COOKIE_BASE64', "")
    if COOKIE_BASE64 != "":
        with open(COOKIE_FILE, "w", encoding="utf-8") as file:
            COOKIE = base64.b64decode(COOKIE_BASE64).decode("utf-8")
            file.write(COOKIE)
            print("\n")
            print(COOKIE)
            print(f"\n\nCookie file saved: {COOKIE_FILE}")

if RESPONSE_TYPE not in ["normal", "stream"]:
    raise BAD_CONFIG_ERROR(f"RESPONSE_TYPE is invalid")
if SUGGEST_MODE not in ["callbackquery", "replykeyboard", "copytext"]:
    raise BAD_CONFIG_ERROR(f"SUGGEST_MODE is invalid")

