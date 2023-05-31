# -*- coding: utf-8 -*-

import re
import sys, importlib
import json, copy
import time
from typing import Dict, List
import pytz
import logging
import asyncio
import contextlib

import EdgeGPT

# import py3langid as langid
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from datetime import time as datetime_time

from BingImageCreator import ImageGenAsync

from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, \
    ReplyKeyboardRemove, InlineQueryResultPhoto, InlineQueryResultArticle, InputTextMessageContent, \
    InputMediaPhoto

from config import BAD_CONFIG_ERROR, API_ID, API_KEY, BOT_TOKEN, ALLOWED_USER_IDS, SUPER_USER_IDS, COOKIE_FILE, NOT_ALLOW_INFO, \
    BOT_NAME, SUGGEST_MODE, DEFAULT_CONVERSATION_STYLE_TYPE, RESPONSE_TYPE, STREAM_INTERVAL, \
    LOG_LEVEL, LOG_TIMEZONE

RESPONSE_TEMPLATE = """{msg_main}
{msg_ref}
- - - - - - - - -
{msg_throttling}
"""

# 设置日志记录级别和格式，创建 logger
class MyFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=pytz.timezone(LOG_TIMEZONE))
        if datefmt:
            return dt.strftime(datefmt)
        else:
            return dt.isoformat()

myformatter = MyFormatter(fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
# 配置日志文件，使用 utc=True 和 atTime=atTime 根据时区设置日志文件(thanks for Bing AI)
dt = datetime.now(pytz.timezone(LOG_TIMEZONE))
utc_offset = dt.utcoffset()
atTime = (datetime.combine(dt, datetime_time(0)) - utc_offset).time()
file_handler = TimedRotatingFileHandler(
    "logs/" + __file__.split("/")[-1].split("\\")[-1].split(".")[0] + ".log", 
    when="MIDNIGHT", 
    interval=1, 
    backupCount=7, # 保留 7 天备份
    utc=True,
    atTime=atTime
)
file_handler.suffix = '%Y-%m-%d.log'
file_handler.setFormatter(myformatter)
file_handler.setLevel(logging.DEBUG) # 将文件日志记录级别设置为 DEBUG
# 配置屏幕日志
screen_handler = logging.StreamHandler()
screen_handler.setFormatter(myformatter)
screen_handler.setLevel(LOG_LEVEL.upper())

logging.basicConfig(
    level=LOG_LEVEL.upper(),
    handlers=[file_handler, screen_handler]
)
logger = logging.getLogger()


def check_conversation_style(style):
    if style in EdgeGPT.ConversationStyle.__members__:
        return True
    return False

if not check_conversation_style(DEFAULT_CONVERSATION_STYLE_TYPE):
    raise BAD_CONFIG_ERROR(f"DEFAULT_CONVERSATION_STYLE_TYPE is invalid")

# 使用 BOT_TOKEN 登陆 tg 机器人
pyro = Client("PyroEdgeGpt", api_id=API_ID, api_hash=API_KEY, bot_token=BOT_TOKEN)

BING_COOKIE = None
with contextlib.suppress(Exception): # 如果文件不存在，则 BING_COOKIE 为 None
    with open(COOKIE_FILE, 'r', encoding="utf-8") as file:
        BING_COOKIE = json.load(file)
        logger.info(f"BING_COOKIE loaded from {COOKIE_FILE}")

# 初始化 bing AI 会话字典(存储格式 key: user_id, value: edge_bot_config)
EDGES = {}
FILE_HANDLE_USERS = {}

if ALLOWED_USER_IDS != None:
    tmpLoop = asyncio.get_event_loop()
    for user_id in ALLOWED_USER_IDS:
        EDGES[user_id] = {
            "bot": tmpLoop.run_until_complete(EdgeGPT.Chatbot.create(cookies=BING_COOKIE)), # 共用一个 cookie.json 文件
            "style": EdgeGPT.ConversationStyle[DEFAULT_CONVERSATION_STYLE_TYPE],
            "response": RESPONSE_TYPE,
            "interval": STREAM_INTERVAL,
            "suggest": SUGGEST_MODE,
            "bot_name": BOT_NAME,
            "temp": {},
            "images": {},
            "cookies": None,
            "image_U": ""
        }
else:
    logger.warning("Allow everyone mode")
    if BING_COOKIE is not None:
        logger.warning("You set BING_COOKIE to not None, but you allowed everyone to use this bot")
    USER_TEMPLATE = {
        "bot": {}, # 共用一个 cookie.json 文件
        "style": EdgeGPT.ConversationStyle[DEFAULT_CONVERSATION_STYLE_TYPE],
        "response": RESPONSE_TYPE,
        "interval": STREAM_INTERVAL,
        "suggest": SUGGEST_MODE,
        "bot_name": BOT_NAME,
        "temp": {},
        "images": {},
        "cookies": None,
        "image_U": ""
    }
    tmpLoop = asyncio.get_event_loop()
    for user_id in SUPER_USER_IDS:
        EDGES[user_id] = {
            "bot": tmpLoop.run_until_complete(EdgeGPT.Chatbot.create(cookies=BING_COOKIE)), # 共用一个 cookie.json 文件
            "style": EdgeGPT.ConversationStyle[DEFAULT_CONVERSATION_STYLE_TYPE],
            "response": RESPONSE_TYPE,
            "interval": STREAM_INTERVAL,
            "suggest": SUGGEST_MODE,
            "bot_name": BOT_NAME,
            "temp": {},
            "images": {},
            "cookies": None,
            "image_U": ""
        }

# 创建自定义过滤器来判断用户是否拥有机器人访问权限
def is_allowed_filter():
    async def func(_, __, update):
        if ALLOWED_USER_IDS is not None:
            if hasattr(update, "from_user"):
                return int(update.from_user.id) in ALLOWED_USER_IDS
            if hasattr(update, "chat"):
                return int(update.chat.id) in ALLOWED_USER_IDS
            return False
        return True
    return filters.create(func)

def check_inited(uid):
    if uid in EDGES.keys():
        return True
    return False

# start 命令提示信息
@pyro.on_message(filters.command("start") & filters.private)
async def start_handle(bot, update):
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    github_link = "https://github.com/tom-snow/PyroEdgeGPTBot"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Star me on Github", url=github_link)],
    ])
    # 不允许使用的用户返回不允许使用提示
    if ALLOWED_USER_IDS is not None and update.chat.id not in ALLOWED_USER_IDS:
        logger.warning(f"User [{update.chat.id}] is not allowed")
        not_allow_info = NOT_ALLOW_INFO.strip()
        if len(not_allow_info.strip()) == 0:
            return
        not_allow_info = not_allow_info.replace("%user_id%", str(update.chat.id))
        await bot.send_message(chat_id=update.chat.id, text=not_allow_info, reply_markup=keyboard)
        return
    if not check_inited(update.chat.id):
        bot_name = BOT_NAME
    else:
        bot_name = EDGES[update.chat.id]["bot_name"]
    welcome_info = f"Hello, I'm {bot_name}. I'm a telegram bot of Bing AI.\nYou can send /help for more information.\n\n"
    if ALLOWED_USER_IDS is None and not check_inited(update.chat.id):
        logger.info(f"User [{update.chat.id}] not inited")
        welcome_info += "You should send command /new to initialize me first."
    # 返回欢迎消息
    await bot.send_message(chat_id=update.chat.id, text=welcome_info, reply_markup=keyboard)

# help 命令提示信息
@pyro.on_message(filters.command("help") & filters.private & is_allowed_filter())
async def help_handle(bot, update):
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    # 帮助信息字符串
    if not check_inited(update.chat.id):
        bot_name = BOT_NAME
    else:
        bot_name = EDGES[update.chat.id]["bot_name"]
    help_text = f"Hello, I'm {bot_name}, a telegram bot of Bing AI\n"
    help_text += "\nAvailable commands:\n"
    help_text += "/start - Start the bot and show welcome message\n"
    help_text += "/help - Show this message\n"
    help_text += "/reset - Reset the bot, optional args: `creative`, `balanced`, `precise`. If this arg is not provided, keep it set before or default.\n"
    help_text += "    Example: `/reset balanced`\n"
    help_text += "/new - Create new conversation. All same as /reset.\n"
    help_text += "/cookie - Set your own cookies. With argument `clear` to clear your cookies.\n"
    help_text += "/switch - Switch the conversation style.\n"
    help_text += "/interval - Set the stream mode message editing interval. (Unit: second)\n"
    help_text += "/suggest_mode - Set the suggest mode. Available arguments: `callbackquery`, `replykeyboard`, `copytext`\n"
    help_text += "/update - Update the EdgeGPT and reload the bot.\n"
    help_text += "/image_gen - Generate images using your custom prompt. Example: `/image_gen cute cats`\n"
    help_text += "\nInline Query:\n"
    help_text += "`@PyroEdgeGptBot g &lt;prompt> %`. Example: `@PyroEdgeGptBot g cats %`\nGenerate images using your prompt 'cats'.\n"
    help_text += "\n\nPS: You should set your own cookie before using image generator. Otherwise, the image generator will not response.\n"
    await bot.send_message(chat_id=update.chat.id, text=help_text)

# 新建/重置会话
@pyro.on_message(filters.command(["new", "reset"]) & filters.private & is_allowed_filter())
async def reset_handle(bot, update):
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    if not check_inited(update.chat.id):
        EDGES[update.chat.id] = copy.deepcopy(USER_TEMPLATE)
        bot_name = BOT_NAME
        try:
            global BING_COOKIE
            EDGES[update.chat.id]["bot"] = await EdgeGPT.Chatbot.create(cookies=BING_COOKIE)
            reply_text = f"{bot_name}: Initialized scussessfully."
            await update.reply(reply_text)
            return
        except Exception as e:
            logger.exception(f"Failed to initialize for user [{update.chat.id}]")
            del EDGES[update.chat.id]
            reply_text = f"{bot_name}: Failed to initialize.({e})"
            await update.reply(reply_text)
            return
    bot_name = EDGES[update.chat.id]["bot_name"]
    reply_text = f"{bot_name} has been reset."
    if len(update.command) > 1:
        arg = update.command[1]
        if check_conversation_style(arg):
            EDGES[update.chat.id]["style"] = arg
            reply_text += f"{bot_name}: Setted CONVERSATION_STYLE_TYPE to '{arg}'."
            logger.warning(f"User [{update.chat.id}] have set  {arg}")
        else:
            await bot.send_message(chat_id=update.chat.id, text="Available arguments: `creative`, `balanced`, `precise`")
            return
    edge = EDGES[update.chat.id]["bot"]
    logger.info(f"Reset EdgeGPT for user [{update.chat.id}]")
    await edge.reset()
    await update.reply(reply_text)

# 切换回复类型
@pyro.on_message(filters.command("switch") & filters.private & is_allowed_filter())
async def set_response_handle(bot, update):
    if not check_inited(update.chat.id):
        await bot.send_message(chat_id=update.chat.id, text="Please initialize me first.")
        logger.error(f"User [{update.chat.id}] try to switch RESPONSE_TYPE but been rejected (not initialized).")
        return
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    if EDGES[update.chat.id]["response"] == "normal":
        EDGES[update.chat.id]["response"] = "stream"
    else:
        EDGES[update.chat.id]["response"] = "normal"
    bot_name = EDGES[update.chat.id]["bot_name"]
    reply_text = f"{bot_name}: Switched RESPONSE_TYPE to '{EDGES[update.chat.id]['response']}'."
    await bot.send_message(chat_id=update.chat.id, text=reply_text)

# 更新依赖
@pyro.on_message(filters.command("update") & filters.private & is_allowed_filter())
async def set_update_handle(bot, update):
    if update.chat.id not in SUPER_USER_IDS:
        await bot.send_message(chat_id=update.chat.id, text="Not Allowed.")
        logger.error(f"User [{update.chat.id}] try to update EdgeGPT but been rejected (not initialized).")
        return
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    bot_name = EDGES[update.chat.id]["bot_name"]
    msg = await bot.send_message(chat_id=update.chat.id
                                 , text=f"{bot_name}: Updateing [EdgeGPT](https://github.com/acheong08/EdgeGPT)."
                                 , disable_web_page_preview=True) 
    # 关闭连接
    for user_id in EDGES:
        await EDGES[user_id]["bot"].close()
    # 更新&重载依赖
    python_path = sys.executable
    executor = await asyncio.create_subprocess_shell(f"{python_path} -m pip install -U EdgeGPT BingImageCreator"
                                                     , stdout=asyncio.subprocess.PIPE
                                                     , stderr=asyncio.subprocess.PIPE
                                                     , stdin=asyncio.subprocess.PIPE)
    stdout, stderr = await executor.communicate()
    logger.info(f"[set_update_handle] stdout: {stdout.decode()}")
    result = ""
    edgegpt_old_version = ""
    edgegpt_new_version = ""
    image_old_version = ""
    image_new_version = ""
    for line in stdout.decode().split("\n"): # 解析日志
        # pkg_resources.get_distribution("BingImageCreator").version
        if "Successfully uninstalled EdgeGPT-" in line:
            edgegpt_old_version = line.replace("Successfully uninstalled EdgeGPT-", "").strip()
        if "Successfully uninstalled BingImageCreator-" in line:
            image_old_version = line.replace("Successfully uninstalled BingImageCreator-", "").strip()
        if "Successfully installed" in line:
            import re
            try:
                edgegpt_new_version = re.findall(r"(?<=EdgeGPT-)(\d+\.\d+\.\d+)", line)[0]
            except:
                logger.exception(f"Warn: Failed to parse EdgeGPT new version: {line}")
            try:
                image_new_version = re.findall(r"(?<=BingImageCreator-)(\d+\.\d+\.\d+)", line)[0]
            except:
                logger.exception(f"Warn: Failed to parse BingImageCreator new version: {line}")
    if edgegpt_old_version and edgegpt_new_version:
        result += f"[EdgeGPT](https://github.com/acheong08/EdgeGPT): {edgegpt_old_version} -> {edgegpt_new_version}\n"
    else:
        result += f"[EdgeGPT](https://github.com/acheong08/EdgeGPT): already the newest version.\n"
    if image_old_version and image_new_version:
        result += f"[BingImageCreator](https://github.com/acheong08/BingImageCreator): {image_old_version} -> {image_new_version}\n"
    else:
        result += f"[BingImageCreator](https://github.com/acheong08/BingImageCreator): already the newest version.\n"
    err = False
    if "WARNING" not in stderr.decode():
        err = True
    if err:
        logger.error(f"[set_update_handle] stderr: {stderr.decode()}")
        result += stderr.decode()
    else:
        logger.warning(f"[set_update_handle] stderr: {stderr.decode()}")

    importlib.reload(EdgeGPT)
    # 重新连接
    for user_id in EDGES:
        cookie = EDGES[user_id]["cookies"] or BING_COOKIE
        EDGES[user_id]["bot"] = await EdgeGPT.Chatbot.create(cookies=cookie)
        EDGES[user_id]["style"] = EdgeGPT.ConversationStyle[DEFAULT_CONVERSATION_STYLE_TYPE]
    bot_name = EDGES[update.chat.id]["bot_name"]
    await msg.edit_text(f"{bot_name}: Updated!\n\n{result}", disable_web_page_preview=True) 

# 设置 用户cookie
@pyro.on_message(filters.command("cookie") & filters.private & is_allowed_filter())
async def set_cookie_handle(bot, update):
    if not check_inited(update.chat.id):
        await bot.send_message(chat_id=update.chat.id, text="Please initialize me first.")
        logger.warning(f"User [{update.chat.id}] try to set cookie but been rejected (not initialized).")
        return
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    left_time = 300
    bot_name = EDGES[update.chat.id]["bot_name"]
    if len(update.command) > 1 and update.command[1] == "clear":
        EDGES[update.chat.id]["cookies"] = ""
        EDGES[update.chat.id]["image_U"] = ""
        await bot.send_message(chat_id=update.chat.id, text=f"{bot_name}: Cookie cleared.")
        return
    msg_text = "{bot_name}: Please send a json file of your cookies in {left_time} seconds.\n\n(This cookie will be used only for you.)"
    msg = await bot.send_message(chat_id=update.chat.id, text=msg_text.format(bot_name=bot_name, left_time=left_time))
    
    logger.info(f"[{update.chat.id}] Allowed to use cookie_file_handle.")
    FILE_HANDLE_USERS[update.chat.id] = True
    loop = asyncio.get_event_loop()
    async def rm_handle_func():
        nonlocal left_time
        if left_time > 10:
            if not FILE_HANDLE_USERS[update.chat.id]: # 已经更新 cookie 后结束
                await msg.delete()
                return True
            left_time -= 10
            await msg.edit_text(msg_text.format(bot_name=bot_name, left_time=left_time))
            loop.call_later(10, callback)
        else:
            logger.warning(f"[{update.chat.id}] Wait for cookie file timeout.")
            FILE_HANDLE_USERS[update.chat.id] = False
            await msg.edit_text(f"{bot_name}: Wait for cookie file timeout!")
        return True
    def callback():
        loop.create_task(rm_handle_func())
    loop.call_later(10, callback)

@pyro.on_message(filters.document & filters.private & is_allowed_filter())
async def cookie_file_handle(bot, update):
    if not check_inited(update.chat.id):
        await bot.send_message(chat_id=update.chat.id, text="Please initialize me first.")
        logger.warning(f"User [{update.chat.id}] try to set cookie but been rejected (not initialized).")
        return
    if update.chat.id  not in FILE_HANDLE_USERS or not FILE_HANDLE_USERS[update.chat.id]:
        logger.warning(f"User [{update.chat.id}] try to set cookie but been rejected (not use /cookie command first).")
        return
    logger.info(f"User [{update.chat.id}] send a file [{update.document.file_name}, {update.document.mime_type}, {update.document.file_size}].")
    if update.document.mime_type != "application/json": # 非 json 格式判断
        await bot.send_message(chat_id=update.chat.id, text=f"Please send a json file. Received ({update.document.mime_type}).")
        return
    cookie_f = await bot.download_media(update.document.file_id, in_memory=True)
    try: # 加载 json
        cookies = json.loads(bytes(cookie_f.getbuffer()).decode("utf-8"))
    except Exception as e:
        logger.exception(f"User [{update.chat.id}] send a non json file")
        await bot.send_message(chat_id=update.chat.id, text="Load json file failed, You should send a json file.")
        return
    cookie_keys = set(["domain", "path", "name", "value"])
    for cookie in cookies: # 检查 cookie 格式
        if cookie_keys & set(cookie.keys()) != cookie_keys:
            logger.warning(f"User [{update.chat.id}] send invalid cookie file!")
            await bot.send_message(chat_id=update.chat.id, text=f"Seems cookie is invalid. Please send a valid cookie json file.")
            return
        if "bing.com" not in cookie["domain"]:
            logger.warning(f"User [{update.chat.id}] send the cookie file not from bing.com!")
            await bot.send_message(chat_id=update.chat.id, text=f"Seems cookie is invalid (not from bing.com). Please send a valid cookie json file.")
            return
    await EDGES[update.chat.id]["bot"].close()
    EDGES[update.chat.id]["cookies"] = cookies
    for cookie in cookies:
        if cookie.get("name") == "_U":
            EDGES[update.chat.id]["image_U"] = cookie.get("value")
            break
    EDGES[update.chat.id]["bot"] = await EdgeGPT.Chatbot.create(cookies=cookies)
    FILE_HANDLE_USERS[update.chat.id] = False
    bot_name = EDGES[update.chat.id]["bot_name"]
    await bot.send_message(chat_id=update.chat.id, text=f"{bot_name}: Cookie set successfully.")

# 设置 stream 模式消息更新间隔
@pyro.on_message(filters.command("interval") & filters.private & is_allowed_filter())
async def set_interval_handle(bot, update):
    if not check_inited(update.chat.id):
        await bot.send_message(chat_id=update.chat.id, text="Please initialize me first.")
        logger.warning(f"User [{update.chat.id}] try to set INTERVAL but been rejected (not initialized).")
        return
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    bot_name = EDGES[update.chat.id]["bot_name"]
    if len(update.command) > 1:
        arg = update.command[1]
        EDGES[update.chat.id]["interval"] = int(arg)
        reply_text = f"{bot_name} has been set INTERVAL to '{arg}'."
        logger.warning(f"User [{update.chat.id}] have set  {arg}")
        await bot.send_message(chat_id=update.chat.id, text=reply_text)
    else:
        reply_text = f"{bot_name}: need an argument 'INTERVAL' (Integer)."
        logger.warning(f"User [{update.chat.id}] need an argument 'INTERVAL' (Integer).")
        await bot.send_message(chat_id=update.chat.id, text=reply_text)

# 设置 bot 名称
@pyro.on_message(filters.command("bot_name") & filters.private & is_allowed_filter())
async def set_interval_handle(bot, update):
    if not check_inited(update.chat.id):
        await bot.send_message(chat_id=update.chat.id, text="Please initialize me first.")
        logger.warning(f"User [{update.chat.id}] try to set INTERVAL but been rejected (not initialized).")
        return
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    bot_name = EDGES[update.chat.id]["bot_name"]
    if len(update.command) > 1:
        arg = update.command[1]
        EDGES[update.chat.id]["bot_name"] = arg
        reply_text = f"{bot_name} has been set 'BOT_NAME' to '{arg}'."
        logger.warning(f"User [{update.chat.id}] have set 'BOT_NAME' to {arg}")
        await bot.send_message(chat_id=update.chat.id, text=reply_text)
    else:
        reply_text = f"{bot_name}: need an argument 'BOT_NAME' (String)."
        logger.warning(f"User [{update.chat.id}] need an argument 'BOT_NAME' (String).")
        await bot.send_message(chat_id=update.chat.id, text=reply_text)

# 修改建议消息模式
@pyro.on_message(filters.command("suggest_mode") & filters.private & is_allowed_filter())
async def set_suggest_mode_handle(bot, update):
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    if not check_inited(update.chat.id):
        await bot.send_message(chat_id=update.chat.id, text="Please initialize me first.")
        logger.warning(f"User [{update.chat.id}] try to set SUGGEST_MODE but been rejected (not initialized).")
        return
    if len(update.command) > 1:
        arg = update.command[1]
        EDGES[update.chat.id]["suggest"] = arg
        if arg in ["callbackquery", "replykeyboard", "copytext"]:
            bot_name = EDGES[update.chat.id]["bot_name"]
            reply_text = f"{bot_name}: set SUGGEST_MODE to '{EDGES[update.chat.id]['suggest']}'."
            await bot.send_message(chat_id=update.chat.id, text=reply_text, reply_markup=ReplyKeyboardRemove())
            return
    reply_text = f"Available arguments: `callbackquery`, `replykeyboard`, `copytext`"
    await bot.send_message(chat_id=update.chat.id, text=reply_text)

def can_image_gen():
    async def funcc(_, __, update):
        global EDGES
        return EDGES[update.chat.id]["image_U"] != "" 
    return filters.create(funcc)
# 图片生成
@pyro.on_message(filters.command("image_gen") & filters.private & is_allowed_filter() & can_image_gen())
async def set_suggest_mode_handle(bot, update):
    if not check_inited(update.chat.id):
        await bot.send_message(chat_id=update.chat.id, text="Please initialize me first.")
        logger.warning(f"User [{update.chat.id}] try to use image_gen but been rejected (not initialized).")
        return
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    if len(update.command) > 1:
        chat_id = update.chat.id
        prompt = " ".join(update.command[1:])
        caption = f"ImageGenerator\nImage is generating, this is a placeholder image.\n\nUsing Prompt: {prompt}"
        msgs = await bot.send_media_group(chat_id, [
            InputMediaPhoto("assets/placeholder0.png", caption=caption),
            InputMediaPhoto("assets/placeholder1.png", caption=caption),
            InputMediaPhoto("assets/placeholder2.png", caption=caption),
            InputMediaPhoto("assets/placeholder3.png", caption=caption),
        ])

        try:
            image_gen_cookie_u = EDGES[chat_id]["image_U"]
            all_cookies = EDGES[update.from_user.id]["cookies"]
            images = await image_gen_main(prompt, image_gen_cookie_u, all_cookies=all_cookies)
            caption = f"ImageGenerator\nImage is generated.\n\nUsing Prompt: {prompt}"
            images_count = len(images)
            for i in range(len(msgs)):
                msg_chat_id = msgs[i].chat.id
                msg_id = msgs[i].id
                if i < images_count:
                    await bot.edit_message_media(msg_chat_id, msg_id, InputMediaPhoto(images[i], caption=caption))
                else:
                    await msgs[i].delete()
            logger.info(f"ImageGenerator Successfully, chat_id: {chat_id}, images({images_count}): {images}")
            return
        except Exception as e:
            logger.exception(f"ImageGenerator Error: {e}")
            await bot.send_message(chat_id=chat_id, text=f"ImageGenerator Error: {e}.\n\nImageGenerator Usage: `/image_gen &lt;prompt>`")
            return
    await update.reply(text="ImageGenerator Usage: `/image_gen &lt;prompt>`")


def is_chat_text_filter():
    async def funcc(_, __, update):
        if bool(update.text):
            return not update.text.startswith("/")
        return False
    return filters.create(funcc)

# 处理文字对话
@pyro.on_message(is_chat_text_filter() & filters.private & is_allowed_filter())
async def chat_handle(bot, update):
    logger.info(f"Receive text [{update.text}] from [{update.chat.id}]")
    if not check_inited(update.chat.id):
        await bot.send_message(chat_id=update.chat.id, text="Please initialize me first.")
        logger.warning(f"User [{update.chat.id}] not inited")
        return
    # 调用 AI
    bot_name = EDGES[update.chat.id]["bot_name"]
    response = f"{bot_name} is thinking..."
    msg = await update.reply(text=response)
    if EDGES[update.chat.id]["response"] == "normal":
        response, reply_markup = await bingAI(update.chat.id, update.text)
        await msg.edit(text=response, reply_markup=reply_markup)
    elif EDGES[update.chat.id]["response"]  == "stream":
        try:
            async for final, response, reply_markup in bingAIStream(update.chat.id, update.text):
                if final:
                    await msg.edit(text=response, reply_markup=reply_markup)
                else:
                    if response == "":
                        continue
                    try:
                        await msg.edit(text=response)
                    except Exception as e: # 有时由于 API 返回数据问题，编辑前后消息内容一致，不做处理，只记录 warning
                        logger.exception(f"Message editing error: {e}")
        except Exception as e:
            logger.error(f"There seems an error at upsteam library, update the upsteam may help.")
            logger.exception(f"[chat_handle, unexpected error]: {e}")
            await msg.edit(text=f"Something went wrong, please check the logs.\n\n[{e}]")
            raise e

# 处理 callback query
@pyro.on_callback_query(is_allowed_filter())
async def callback_query_handle(bot, query):
    if not check_inited(query.from_user.id):
        await bot.send_message(chat_id=query.from_user.id, text="Please initialize me first.")
        logger.warning(f"User [{query.from_user.id}] try to send callback query but been rejected (not initialized).")
        return
    query_text = EDGES[query.from_user.id]["temp"].get(query.data)
    logger.info(f"Receive callback query [{query.data}: {query_text}] from [{query.from_user.id}]")
    if query_text is None:
        # 重启 bot 后会丢失之前存储的 callback query 对应信息，暂时返回报错让用户手动发消息（后续将 callback query 存储在数据库中，而不是内存）
        await bot.send_message(chat_id=query.from_user.id, text="Sorry, the callback query is not found.(May be you have restarted the bot before.)")
        return
    # 调用 AI
    bot_name = EDGES[query.from_user.id]["bot_name"]
    response = f"{bot_name} is thinking..."
    msg = await bot.send_message(chat_id=query.from_user.id, text=response)
    if EDGES[query.from_user.id]["response"] == "normal":
        response, reply_markup = await bingAI(query.from_user.id, query_text)
        await msg.edit(text=response, reply_markup=reply_markup)
    elif EDGES[query.from_user.id]["response"] == "stream":
        try:
            async for final, response, reply_markup in bingAIStream(query.from_user.id, query_text):
                if final:
                    await msg.edit(text=response, reply_markup=reply_markup)
                else:
                    if response == "":
                        continue
                    await msg.edit(text=response)
        except Exception as e:
            logger.error("There seems an error at upsteam library, update the upsteam may help.")
            logger.exception(f"[callback_query_handle, unexpected error]: {e}")
            await msg.edit(text=f"Something went wrong, please check the logs.\n\n[{e}]")
            raise e

def is_image_gen_query_filter():
    async def funcg(_, __, update):
        if update.query.startswith("g"):
            global EDGES
            return EDGES[update.from_user.id]["image_U"] != ""
        return False
    return filters.create(funcg)

@pyro.on_inline_query(is_allowed_filter() & is_image_gen_query_filter())
async def inline_query_image_gen_handle(bot, update):
    """
    You should enable 'Inline Mode' and set 'Inline Feedback' to '100%' (10% may works well too) at @BotFather.
    你应该在 @BotFather 上启用 'Inline Mode' 并设置 'Inline Feedback' 为 '100%' (10% 或许也能较好工作)
    """
    if not check_inited(update.from_user.id):
        logger.warning(f"User [{update.from_user.id}] try to send inline_query image_gen but been rejected (not initialized).")
        await update.answer(
            results=[
                InlineQueryResultArticle(
                    title="Not initialized",
                    input_message_content=InputTextMessageContent(
                        "Not initialized"
                    ),
                    description="Please initialize me first.",
                )
            ],
            cache_time=1
        )
        return
    tmp = update.query.split(" ", 1)
    prompt = ""
    if len(tmp) >= 2:
        prompt = tmp[1].strip()
    logger.info(f"Receive inline_query image_gen result [{prompt}] from [{update.from_user.id}]")

    if prompt == "": # 如果没有输入 prompt 返回使用说明提示
        await update.answer(
            results=[
                InlineQueryResultArticle(
                    title="ImageGenerator",
                    input_message_content=InputTextMessageContent(
                        "No prompt provide!\n\nUsage: Use `@BotName g &lt;prompt> %` to generate image. (Tips: If it take long time (25s) no response, you can add a '%' and delete it to refresh)"
                    ),
                    description="Input a prompt to generate an Image",
                )
            ],
            cache_time=1
        )
        return
    
    img = -1
    while True:
        if prompt.endswith("%"):
            prompt = prompt[:-1].strip()
            img += 1
        else:
            break

    # lang = langid.classify(prompt)[0] # 语言判断，现在 Bing AI 已经支持中文，暂时不做判断，其他语言不清楚

    if img == -1: # 如果没有输入 prompt 终止符,则返回提示
        await update.answer(
            results=[
                InlineQueryResultArticle(
                    title="Prompt: " + prompt + "(Add '%' at the end of prompt to generate image)",
                    description="Tips: If it take long time (25s) no response, you can add a '%' and delete it to refresh",
                    input_message_content=InputTextMessageContent(
                        "Please add '%' at the end of prompt to confirm the prompt. Add more (Max: 4) '%' to select next image. (Tips: If it take long time (25s) no response, you can add a '%' and delete it to refresh)"
                    )
                )
            ]
        )
        return
    try:
        prompt_hash = str(hash(prompt))
        if EDGES[update.from_user.id]["images"].get(prompt_hash) is not None:
            images = EDGES[update.from_user.id]["images"].get(prompt_hash)
        else:
            image_gen_cookie_u = EDGES[update.from_user.id]["image_U"]
            all_cookies = EDGES[update.from_user.id]["cookies"]
            images = await image_gen_main(prompt, image_gen_cookie_u, all_cookies=all_cookies) # 获取图片并缓存
            EDGES[update.from_user.id]["images"] = {}
            EDGES[update.from_user.id]["images"][prompt_hash] = images

        if img >= len(images):
            img = len(images) - 1
        img_url = images[img]

        await update.answer(
            results=[
                InlineQueryResultPhoto(
                    title="ImageGeneration Prompt: " + prompt,
                    description="Add more '%' at the end of prompt to select next image",
                    photo_url=img_url,
                    caption=f"This Image is generated by Bing AI with prompt: {prompt}",
                )
            ],
            cache_time=1
        )
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        logger.exception(f"[inline_query_image_gen_handle, unexpected error]: {e}")
        await update.answer(
            results=[
                InlineQueryResultArticle(
                    title="[ERROR] Prompt: " + prompt,
                    description=e.__str__(),
                    input_message_content=InputTextMessageContent(
                        f"Something went wrong.\n\nError message: {e.__str__()}\n\nYour Prompt: {prompt}"
                    )
                )
            ]
        )


def is_prompt_select_filter():
    async def funcp(_, __, update):
        return update.query.startswith("p")
    return filters.create(funcp)

@pyro.on_inline_query(is_allowed_filter() & is_prompt_select_filter())
async def inline_query_prompt_select_handle(bot, update):
    """
    You should enable 'Inline Mode' and set 'Inline Feedback' to '100%' (10% may works well too) at @BotFather.
    你应该在 @BotFather 上启用 'Inline Mode' 并设置 'Inline Feedback' 为 '100%' (10% 或许也能较好工作)
    """
    if not check_inited(update.from_user.id):
        logger.warning(f"User [{update.from_user.id}] try to send inline_query prompt select result but been rejected (not initialized).")
        await update.answer(
            results=[
                InlineQueryResultArticle(
                    title="Not initialized",
                    input_message_content=InputTextMessageContent(
                        "Not initialized"
                    ),
                    description="Please initialize me first.",
                )
            ],
            cache_time=1
        )
        return
    tmp = update.query.split(" ", 1)
    query = ""
    if len(tmp) >= 2:
        query = tmp[1]
    logger.info(f"Receive inline_query prompt select result [{query}] from [{update.from_user.id}]")
    await update.answer(
        results=[
            InlineQueryResultArticle(
                title="PromptSelector",
                input_message_content=InputTextMessageContent(
                    "[Not Supported Yet]Use `@BotName p &lt;query>` to select Prompt. You should use this to send message to AI bot."
                ),
                description="[Not Supported Yet]Click me to show usage of PromptSelector",
            )
        ],
        cache_time=1
    )

def is_default_inline_filter():
    async def funcd(_, __, update):
        return not update.query.startswith("p") and not update.query.startswith("g")
    return filters.create(funcd)

@pyro.on_inline_query(is_allowed_filter() & is_default_inline_filter())
async def inline_query_default_handle(bot, update):
    """
    You should enable 'Inline Mode' and set 'Inline Feedback' to '100%' (10% may works well too) at @BotFather.
    你应该在 @BotFather 上启用 'Inline Mode' 并设置 'Inline Feedback' 为 '100%' (10% 或许也能较好工作)
    """
    if not check_inited(update.from_user.id):
        logger.warning(f"User [{update.from_user.id}] try to send inline_query default result but been rejected (not initialized).")
        await update.answer(
            results=[
                InlineQueryResultArticle(
                    title="Not initialized",
                    input_message_content=InputTextMessageContent(
                        "Not initialized"
                    ),
                    description="Please initialize me first.",
                )
            ],
            cache_time=1
        )
        return
    logger.info(f"Receive default result [{update.query}] from [{update.from_user.id}]")
    await update.answer(
        results=[
            InlineQueryResultArticle(
                title="ImageGenerator",
                input_message_content=InputTextMessageContent(
                    # "Usage: Use `@BotName g &lt;prompt>` to generate image. Prompt should be in English, If prompt is not in English, it will automatically use AI to translate prompt to English."
                    "Usage: Use `@BotName g &lt;prompt>` to generate image. (Tips: If it take long time (25s) no response, you can add a '%' and delete it to refresh)"
                ),
                description="Click me to show usage of ImageGenerator",
            ),
            InlineQueryResultArticle(
                title="PromptSelector",
                input_message_content=InputTextMessageContent(
                    "[Not Supported Yet]Use `@BotName p &lt;query>` to select Prompt. You should use this to send message to AI bot."
                ),
                description="[Not Supported Yet]Click me to show usage of PromptSelector",
            )
        ],
        cache_time=1
    )


async def bingAI(user_id, messageText):
    rsp = await EDGES[user_id]["bot"].ask(prompt=messageText, conversation_style=EDGES[user_id]["style"])
    rsp_json = json.dumps(rsp, ensure_ascii=False)
    logger.info(f"BingAI raw response: {rsp_json}")

    response, msg_suggest = process_message_main(rsp, user_id)
    return response, msg_suggest

async def bingAIStream(user_id, messageText):
    last_time = time.time() - 0.5 # 第一次间隔调小(有需要自行根据 EDGES[user_id]["interval"] 调整)
    async for final, rsp in  EDGES[user_id]["bot"].ask_stream(prompt=messageText, conversation_style=EDGES[user_id]["style"]):
        now_time = time.time()
        if final:
            rsp_json = json.dumps(rsp, ensure_ascii=False)
            logger.info(f"BingAI stream response final: {rsp_json}")
            
            response, msg_suggest = process_message_main(rsp, user_id)
            yield final, response, msg_suggest

        if now_time - last_time > EDGES[user_id]["interval"] and not final:
            last_time = now_time
            logger.info(f"BingAI stream response: {rsp}")
            if type(rsp) == str:
                rsp = rsp.strip()
                response = re.sub(r'\[\^(\d+)\^\]', '', rsp)
                if response.startswith("[1]: "): # 删除引用的消息链接, 避免消息闪动幅度过大
                    response = response.split("\n\n", 1)[1]
            else:
                response = "[WARN] BingAI stream response: Returned non-string type data without final"
                logger.warning(f"BingAI stream response: Returned non-string type data without final")
            yield final, response, ""

def process_message_main(rsp_obj, user_id=None):
    response = RESPONSE_TEMPLATE

    # 回复消息主文本部分
    if "messages" in rsp_obj["item"]:
        bot_message = rsp_obj["item"]["messages"][1]
        msg_main, msg_ref, msg_suggest = process_message_body(bot_message, user_id)
    elif "result" in rsp_obj["item"]:
        logger.warning(f"[process_message_main] BingAI result: {json.dumps(rsp_obj['item']['result'], ensure_ascii=False)}")
        if rsp_obj["item"]["result"]["value"] == "InvalidSession":
            response = "Invalid Session (may be session expired), Please /reset the chat"
            return response, None
        elif rsp_obj["item"]["result"]["value"] == "Throttled":
            response = "Request is throttled (You request may contain sensitive content), Please /reset the chat"
            return response, None
        else:
            if "message" in rsp_obj["item"]["result"]:
                response = rsp_obj["item"]["result"]["message"] + "Please /reset the chat"
            response = "Something wrong. Please /reset the chat"
            return response, None
    else:
        logger.warning(f"[process_message_main] BingAI response: {json.dumps(rsp_obj, ensure_ascii=False)}")
        response = "Something wrong. Please /reset the chat"
        return response, None
        
    throttlingMax = rsp_obj["item"]["throttling"]["maxNumUserMessagesInConversation"]
    throttlingUser = rsp_obj["item"]["throttling"]["numUserMessagesInConversation"]
    msg_throttling = f"Messages: {throttlingUser}/{throttlingMax}"
    if throttlingUser >= throttlingMax:
        asyncio.run(EDGES[user_id]["bot"].reset())
        msg_throttling += "\nNote: Conversation is over, and I auto reset it successfully."
    if msg_main == "":
        response = "Something wrong. Please /reset the chat" # default response
    else:
        response = response.format(msg_main=msg_main, msg_ref=msg_ref, msg_throttling=msg_throttling)
    return response, msg_suggest

def process_message_body(msg_obj, user_id=None):
    # 回复消息的主体部分(先设置为空)
    msg_main = ""
    msg_ref = ""
    msg_suggest = None
    if "text" in msg_obj:
        msg_main = msg_obj["text"]
    if "sourceAttributions" in msg_obj:
        source_count = len(msg_obj["sourceAttributions"]) # 可用的引用资源数量
        # 将引用标号与具体引用的链接绑定
        if re.search(r'\[\^(\d+)\^\]', msg_main) is not None:
            matches = re.findall(r'\[\^(\d+)\^\]', msg_main) # 匹配引用标号(类似 "[^1^]" 格式)
            for match in matches: # 对每个引用标号找到实际引用链接并绑定好 markdown 格式链接
                if int(match) > source_count: # 如果“最大引用编号” 大于 “引用资源数量”，则删除它
                    msg_main = msg_main.replace(f"[^{match}^]", "", 1)
                    continue
                url = msg_obj["sourceAttributions"][int(match) - 1]["seeMoreUrl"]
                msg_main = msg_main.replace(f"[^{match}^]", f"[[{match}]]({url})", 1)
            
        # 消息引用部分(参考链接)
        if source_count > 0:
            msg_ref = "- - - - - - - - -\nReference:\n"
        for ref_index in range(source_count):
            providerDisplayName = msg_obj["sourceAttributions"][ref_index]["providerDisplayName"]
            url = msg_obj["sourceAttributions"][ref_index]["seeMoreUrl"]
            msg_ref += f"{ref_index + 1}. [{providerDisplayName}]({url})\n"

    # 建议消息部分
    if "suggestedResponses" in msg_obj:
        suggested_count = len(msg_obj["suggestedResponses"])
        if EDGES[user_id]["suggest"]  == "callbackquery":
            msg_suggest = InlineKeyboardMarkup([])
            EDGES[user_id]["temp"] = {}
            for suggested_index in range(suggested_count):
                suggested_text = msg_obj["suggestedResponses"][suggested_index]["text"]
                suggested_hash = str(hash(suggested_text)) # 使用 hash 值作为 data ，避免 data 过长报错
                EDGES[user_id]["temp"][suggested_hash] = suggested_text
                msg_suggest.inline_keyboard.append([InlineKeyboardButton(suggested_text, callback_data=suggested_hash)])
        elif EDGES[user_id]["suggest"] == "replykeyboard":
            msg_suggest = ReplyKeyboardMarkup([])
            for suggested_index in range(suggested_count):
                suggested_text = msg_obj["suggestedResponses"][suggested_index]["text"]
                msg_suggest.keyboard.append([suggested_text])
        else:
            msg_ref += "- - - - - - - - -\nSuggestion(Click to copy):\n"
            for suggested_index in range(suggested_count):
                suggested_text = msg_obj["suggestedResponses"][suggested_index]["text"]
                msg_ref += f"{suggested_index + 1}. `{suggested_text}`\n"

    return msg_main, msg_ref, msg_suggest

async def image_gen_main(prompt, image_gen_cookie_u, all_cookies: List[Dict] = None):
    if all_cookies is None:
        async with ImageGenAsync(image_gen_cookie_u) as image_generator:
            images = await image_generator.get_images(prompt)
            return images
    else:
        async with ImageGenAsync(image_gen_cookie_u, all_cookies=all_cookies) as image_generator:
            images = await image_generator.get_images(prompt)
            return images



pyro.run()
