# -*- coding: utf-8 -*-

import re
import sys, importlib
import json
import time
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
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, \
    ReplyKeyboardRemove, InlineQueryResultPhoto, InlineQueryResultArticle, InputTextMessageContent, \
    InputMediaPhoto

from config import API_ID, API_KEY, BOT_TOKEN, ALLOWED_USER_IDS, COOKIE_FILE, NOT_ALLOW_INFO, \
    BOT_NAME, SUGGEST_MODE, DEFAULT_CONVERSATION_STYLE_TYPE, RESPONSE_TYPE, STREAM_INTERVAL, \
    LOG_LEVEL, LOG_TIMEZONE

RESPONSE_TEMPLATE = """{msg_main}
{msg_ref}
- - - - - - - - -
{msg_throttling}
"""

IMAGE_GEN_COOKIE_U = ""
with contextlib.suppress(Exception):
    with open(COOKIE_FILE, encoding="utf-8") as file:
        cookie_json = json.load(file)
        for cookie in cookie_json:
            if cookie.get("name") == "_U":
                IMAGE_GEN_COOKIE_U = cookie.get("value")
                break

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

# 配置文件不正确时的异常
class BAD_CONFIG_ERROR(Exception):
    pass

if not API_ID or not API_KEY or not BOT_TOKEN or not ALLOWED_USER_IDS:
    raise BAD_CONFIG_ERROR(f"API_ID, API_KEY, BOT_TOKEN or ALLOWED_USER_IDS is not set")
if not check_conversation_style(DEFAULT_CONVERSATION_STYLE_TYPE):
    raise BAD_CONFIG_ERROR(f"DEFAULT_CONVERSATION_STYLE_TYPE is invalid")
if RESPONSE_TYPE not in ["normal", "stream"]:
    raise BAD_CONFIG_ERROR(f"RESPONSE_TYPE is invalid")
if SUGGEST_MODE not in ["callbackquery", "replykeyboard", "copytext"]:
    raise BAD_CONFIG_ERROR(f"SUGGEST_MODE is invalid")

# 使用 BOT_TOKEN 登陆 tg 机器人
pyro = Client("PyroEdgeGpt", api_id=API_ID, api_hash=API_KEY, bot_token=BOT_TOKEN)

# 初始化 bing AI 会话字典(存储格式 key: user_id, value: edge_bot_config)
EDGES = {}
tmpLoop = asyncio.get_event_loop()
for user_id in ALLOWED_USER_IDS:
    EDGES[user_id] = {
        "bot": tmpLoop.run_until_complete(EdgeGPT.Chatbot.create(cookie_path=COOKIE_FILE)), # 共用一个 cookie.json 文件
        "style": EdgeGPT.ConversationStyle[DEFAULT_CONVERSATION_STYLE_TYPE],
        "response": RESPONSE_TYPE,
        "interval": STREAM_INTERVAL,
        "suggest": SUGGEST_MODE,
        "temp": {},
        "images": {}
    }

# 创建自定义过滤器来判断用户是否拥有机器人访问权限
def is_allowed_filter():
    async def func(_, __, update):
        return int(update.from_user.id) in ALLOWED_USER_IDS
    return filters.create(func)

# start 命令提示信息
@pyro.on_message(filters.command("start") & filters.private)
async def start_handle(bot, update):
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    github_link = "https://github.com/tom-snow/PyroEdgeGPTBot"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Star me on Github", url=github_link)],
    ])
    # 不允许使用的用户返回不允许使用提示
    if int(update.chat.id) not in ALLOWED_USER_IDS:
        not_allow_info = NOT_ALLOW_INFO.strip()
        if len(not_allow_info.strip()) == 0:
            return
        not_allow_info = not_allow_info.replace("%user_id%", str(update.chat.id))
        await bot.send_message(chat_id=update.chat.id, text=not_allow_info, reply_markup=keyboard)
        return
    # 返回欢迎消息
    await bot.send_message(chat_id=update.chat.id, text=f"Hello, I'm {BOT_NAME}.", reply_markup=keyboard)

# help 命令提示信息
@pyro.on_message(filters.command("help") & filters.private & filters.chat(ALLOWED_USER_IDS))
async def help_handle(bot, update):
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    # 帮助信息字符串
    help_text = f"Hello, I'm {BOT_NAME}, a telegram bot of Bing AI\n"
    help_text += "\nAvailable commands:\n"
    help_text += "/start - Start the bot and show welcome message\n"
    help_text += "/help - Show this message\n"
    help_text += "/reset - Reset the bot, optional args: `creative`, `balanced`, `precise`. If this arg is not provided, keep it set before or default.\n"
    help_text += "    Example: `/reset balanced`\n"
    help_text += "/new - Create new conversation. All same as /reset.\n"
    help_text += "/switch - Switch the conversation style.\n"
    help_text += "/interval - Set the stream mode message editing interval. (Unit: second)\n"
    help_text += "/suggest_mode - Set the suggest mode. Available arguments: `callbackquery`, `replykeyboard`, `copytext`\n"
    await bot.send_message(chat_id=update.chat.id, text=help_text)

# 新建/重置会话
@pyro.on_message(filters.command(["new", "reset"]) & filters.private & filters.chat(ALLOWED_USER_IDS))
async def reset_handle(bot, update):
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    reply_text = f"{BOT_NAME} has been reset."
    if len(update.command) > 1:
        arg = update.command[1]
        if check_conversation_style(arg):
            EDGES[update.chat.id]["style"] = arg
            reply_text = f"{BOT_NAME} has been reset. set CONVERSATION_STYLE_TYPE to '{arg}'."
            logger.warning(f"User [{update.chat.id}] have set  {arg}")
        else:
            await bot.send_message(chat_id=update.chat.id, text="Available arguments: `creative`, `balanced`, `precise`")
            return
    edge = EDGES[int(update.chat.id)]["bot"]
    await edge.reset()
    await update.reply(reply_text)

# 切换回复类型
@pyro.on_message(filters.command("switch") & filters.private & filters.chat(ALLOWED_USER_IDS))
async def set_response_handle(bot, update):
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    if EDGES[update.chat.id]["response"] == "normal":
        EDGES[update.chat.id]["response"] = "stream"
    else:
        EDGES[update.chat.id]["response"] = "normal"
    reply_text = f"{BOT_NAME}: set RESPONSE_TYPE to '{EDGES[update.chat.id]['response']}'."
    await bot.send_message(chat_id=update.chat.id, text=reply_text)

# 更新依赖
@pyro.on_message(filters.command("update") & filters.private & filters.chat(ALLOWED_USER_IDS))
async def set_update_handle(bot, update):
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    msg = await bot.send_message(chat_id=update.chat.id
                                 , text=f"{BOT_NAME}: Updateing [EdgeGPT](https://github.com/acheong08/EdgeGPT)."
                                 , disable_web_page_preview=True) 
    # 关闭连接
    for user_id in EDGES:
        await EDGES[user_id]["bot"].close()
    # 更新&重载依赖
    python_path = sys.executable
    executor = await asyncio.create_subprocess_shell(f"{python_path} -m pip install -U EdgeGPT"
                                                     , stdout=asyncio.subprocess.PIPE
                                                     , stderr=asyncio.subprocess.PIPE
                                                     , stdin=asyncio.subprocess.PIPE)
    stdout, stderr = await executor.communicate()
    logger.info(f"[set_update_handle] stdout: {stdout.decode()}")
    result = ""
    old_version = ""
    new_version = ""
    for line in stdout.decode().split("\n"): # 解析日志
        if "Successfully uninstalled EdgeGPT-" in line:
            old_version = line.replace("Successfully uninstalled EdgeGPT-", "").strip()
        if "Successfully installed EdgeGPT-" in line:
            new_version = line.replace("Successfully installed EdgeGPT-", "").strip()
    if old_version and new_version:
        result = f"[EdgeGPT](https://github.com/acheong08/EdgeGPT): {old_version} -> {new_version}"
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
        EDGES[user_id]["bot"] = await EdgeGPT.Chatbot.create(cookie_path=COOKIE_FILE)
        EDGES[user_id]["style"] = EdgeGPT.ConversationStyle[DEFAULT_CONVERSATION_STYLE_TYPE]
    await msg.edit_text(f"{BOT_NAME}: Updated!\n\n{result}", disable_web_page_preview=True) 

# 设置 stream 模式消息更新间隔
@pyro.on_message(filters.command("interval") & filters.private & filters.chat(ALLOWED_USER_IDS))
async def set_interval_handle(bot, update):
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    if len(update.command) > 1:
        arg = update.command[1]
        EDGES[update.chat.id]["interval"] = int(arg)
        reply_text = f"{BOT_NAME} has been set INTERVAL to '{arg}'."
        logger.warning(f"User [{update.chat.id}] have set  {arg}")
        bot.send_message(chat_id=update.chat.id, text=reply_text)

# 修改建议消息模式
@pyro.on_message(filters.command("suggest_mode") & filters.private & filters.chat(ALLOWED_USER_IDS))
async def set_suggest_mode_handle(bot, update):
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    if len(update.command) > 1:
        arg = update.command[1]
        EDGES[update.chat.id]["suggest"] = arg
        if arg in ["callbackquery", "replykeyboard", "copytext"]:
            reply_text = f"{BOT_NAME}: set SUGGEST_MODE to '{EDGES[update.chat.id]['suggest']}'."
            await bot.send_message(chat_id=update.chat.id, text=reply_text, reply_markup=ReplyKeyboardRemove())
            return
    reply_text = f"Available arguments: `callbackquery`, `replykeyboard`, `copytext`"
    await bot.send_message(chat_id=update.chat.id, text=reply_text)

def can_image_gen():
    async def funcc(_, __, update):
        return IMAGE_GEN_COOKIE_U != ""
    return filters.create(funcc)
# 图片生成
@pyro.on_message(filters.command("image_gen") & filters.private & filters.chat(ALLOWED_USER_IDS) & can_image_gen())
async def set_suggest_mode_handle(bot, update):
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    if len(update.command) > 1:
        chat_id = update.chat.id
        placeholder0 = "AgACAgQAAxkBAAMIZFFEWtUdu7y7O0W02C0dI7Q50xYAArS6MRuV0YFSDLuenqIQy8gACAEAAwIAA3gABx4E" # assets/placeholder0.png
        placeholder1 = "AgACAgQAAxkBAAMJZFFEjKiGPDzKAqGm8jUGXXxXqWIAAhu7MRtskYlScm9aBotskTgACAEAAwIAA3gABx4E" # assets/placeholder1.png
        placeholder2 = "AgACAgQAAxkBAAMKZFFEsD-xr4r89Jm10Dg-2GK6pdIAAhy7MRtskYlSeYXuodobO3YACAEAAwIAA3gABx4E" # assets/placeholder2.png
        placeholder3 = "AgACAgQAAxkBAAMLZFFEzEhkfH2kM-Gyx-5j8KrG5YgAAh27MRtskYlSKctsbQ4wl14ACAEAAwIAA3gABx4E" # assets/placeholder3.png
        prompt = update.command[1:]
        caption = f"ImageGenerator\nImage is generating, this is a placeholder image.\n\nUsing Prompt: {prompt}"
        try:
            msgs = await bot.send_media_group(chat_id, [
                InputMediaPhoto(placeholder0, caption=caption),
                InputMediaPhoto(placeholder1, caption=caption),
                InputMediaPhoto(placeholder2, caption=caption),
                InputMediaPhoto(placeholder3, caption=caption)
            ])
        except Exception as e:
            logger.warning(f"ImageGenerator Send Default Placeholder Image Warn: {e}")
            msgs = await bot.send_media_group(chat_id, [
                InputMediaPhoto("assets/placeholder0.png", caption=caption),
                InputMediaPhoto("assets/placeholder1.png", caption=caption),
                InputMediaPhoto("assets/placeholder2.png", caption=caption),
                InputMediaPhoto("assets/placeholder3.png", caption=caption),
            ])

        try:
            images = await image_gen_main(prompt)
            caption = f"ImageGenerator\nImage is generated.\n\nUsing Prompt: {prompt}"
            images_count = len(images)
            for i in range(len(msgs)):
                msg_chat_id = msgs[i].chat.id
                msg_id = msgs[i].id
                if i < images_count:
                    await bot.edit_message_media(msg_chat_id, msg_id, InputMediaPhoto(images[i], caption=caption))
                else:
                    await msgs[i].delete()
            logger.info(f"ImageGenerator Successfully, chat_id: {chat_id}, images: {images}")
            return
        except Exception as e:
            logger.error(f"ImageGenerator Error: {e}")
            await bot.send_message(chat_id=chat_id, text=f"ImageGenerator Error: {e}.\n\nImageGenerator Usage: `/image_gen &lt;prompt>`")
            return
    await update.reply(text="ImageGenerator Usage: `/image_gen &lt;prompt>`")

# 处理文字对话
@pyro.on_message(filters.text & filters.private & filters.chat(ALLOWED_USER_IDS))
async def chat_handle(bot, update):
    logger.info(f"Receive text [{update.text}] from [{update.chat.id}]")
    # 调用 AI
    response = f"{BOT_NAME} is thinking..."
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
                        logger.warning(f"Message editing error: {e}")
        except Exception as e:
            logger.error(f"[chat_handle, unexpected error]: {e}")
            await msg.edit(text="Something went wrong, please check the logs.")
            raise e

# 处理 callback query
@pyro.on_callback_query(is_allowed_filter())
async def callback_query_handle(bot, query):
    query_text = EDGES[query.from_user.id]["temp"].get(query.data)
    logger.info(f"Receive callback query [{query.data}: {query_text}] from [{query.from_user.id}]")
    if query_text is None:
        # 重启 bot 后会丢失之前存储的 callback query 对应信息，暂时返回报错让用户手动发消息（后续将 callback query 存储在数据库中，而不是内存）
        await bot.send_message(chat_id=query.from_user.id, text="Sorry, the callback query is not found.(May be you have restarted the bot before.)")
        return
    # 调用 AI
    response = f"{BOT_NAME} is thinking..."
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
            logger.error(f"[callback_query_handle, unexpected error]: {e}")
            await msg.edit(text="Something went wrong, please check the logs.")
            raise e


def is_image_gen_query_filter():
    async def funcg(_, __, update):
        if update.query.startswith("g"):
            return IMAGE_GEN_COOKIE_U != ""
        return False
    return filters.create(funcg)

@pyro.on_inline_query(is_allowed_filter() & is_image_gen_query_filter())
async def inline_query_image_gen_handle(bot, update):
    """
    You should enable 'Inline Mode' and set 'Inline Feedback' to '100%' (10% may works well too) at @BotFather.
    你应该在 @BotFather 上启用 'Inline Mode' 并设置 'Inline Feedback' 为 '100%' (10% 或许也能较好工作)
    """
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
            images = await image_gen_main(prompt) # 获取图片并缓存
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

        if now_time - last_time > EDGES[user_id]["interval"]:
            last_time = now_time
            logger.info(f"BingAI stream response: {rsp}")
            response = re.sub(r'\[\^(\d+)\^\]', '', rsp)
            if response.startswith("[1]: "): # 删除引用的消息链接, 避免消息闪动幅度过大
                response = response.split("\n\n", 1)[1]
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

async def image_gen_main(prompt):
    async with ImageGenAsync(IMAGE_GEN_COOKIE_U) as image_generator:
        images = await image_generator.get_images(prompt)
        return images


pyro.run()
