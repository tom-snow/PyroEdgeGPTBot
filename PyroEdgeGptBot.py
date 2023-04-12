# -*- coding: utf-8 -*-
import re
import json
import time
import logging
import asyncio

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from EdgeGPT import Chatbot, ConversationStyle

from config import API_ID, API_KEY, BOT_TOKEN, ALLOWED_USER_IDS, COOKIE_FILE, NOT_ALLOW_INFO, \
    BOT_NAME, SUGGEST_MODE, DEFAULT_CONVERSATION_STYLE_TYPE, RESPONSE_TYPE, STREAM_INTERVAL, LOG_LEVEL

RESPONSE_TEMPLATE = """{msg_main}
{msg_ref}
- - - - - - - - -
{msg_throttling}
"""

# 设置日志记录级别和格式，创建 logger
logging.basicConfig(
    level=LOG_LEVEL.upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__file__)

def check_conversation_style(style):
    if style in ConversationStyle.__members__:
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
for user_id in ALLOWED_USER_IDS:
    EDGES[user_id] = {
        "bot": Chatbot(cookiePath=COOKIE_FILE), # 共用一个 cookie.json 文件
        "style": ConversationStyle[DEFAULT_CONVERSATION_STYLE_TYPE],
        "response": RESPONSE_TYPE,
        "interval": STREAM_INTERVAL,
        "suggest": SUGGEST_MODE,
        "temp": {}
    }

# 创建自定义过滤器来判断用户是否拥有机器人访问权限
def is_allowed_filter():
    async def func(_, __, query):
        return int(query.from_user.id) in ALLOWED_USER_IDS
    return filters.create(func)

# start 命令提示信息
@pyro.on_message(filters.command("start") & filters.private)
async def start_handle(bot, update):
    logger.info(f"Receive commands [{update.command}] from [{update.chat.id}]")
    # 不允许使用的用户返回不允许使用提示
    if int(update.chat.id) not in ALLOWED_USER_IDS:
        not_allow_info = NOT_ALLOW_INFO.strip()
        if len(not_allow_info.strip()) == 0:
            return
        not_allow_info = not_allow_info.replace("%user_id%", str(update.chat.id))
        await bot.send_message(chat_id=update.chat.id, text=not_allow_info)
        return
    # 返回欢迎消息
    github_link = "https://github.com/tom-snow/PyroEdgeGPTBot"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Star me on Github", url=github_link)],
    ])
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

# 处理文字对话
@pyro.on_message(filters.text & filters.private & filters.chat(ALLOWED_USER_IDS))
async def chat_handle(bot, update):
    logger.info(f"Receive text [{update.text}] from [{update.chat.id}]")
    # 调用 AI
    response = f"{BOT_NAME} is thinking..."
    if EDGES[update.chat.id]["response"] == "normal":
        msg = await update.reply(text=response)
        response, reply_markup = await bingAI(update.chat.id, update.text)
        await msg.edit(text=response, reply_markup=reply_markup)
    elif EDGES[update.chat.id]["response"]  == "stream":
        msg = await update.reply(text=response)
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

# 处理 callback query
@pyro.on_callback_query(is_allowed_filter())
async def callback_query_handle(bot, query):
    query_text = EDGES[query.from_user.id]["temp"].get(query.data)
    logger.info(f"Receive callback query [{query.data}: {query_text}] from [{query.from_user.id}]")
    # 调用 AI
    response = f"{BOT_NAME} is thinking..."
    if EDGES[query.from_user.id]["response"] == "normal":
        msg = await bot.send_message(chat_id=query.from_user.id, text=response)
        response, reply_markup = await bingAI(query.from_user.id, query_text)
        await msg.edit(text=response, reply_markup=reply_markup)
    elif EDGES[query.from_user.id]["response"] == "stream":
        msg = await bot.send_message(chat_id=query.from_user.id, text=response)
        async for final, response, reply_markup in bingAIStream(query.from_user.id, query_text):
            if final:
                await msg.edit(text=response, reply_markup=reply_markup)
            else:
                if response == "":
                    continue
                await msg.edit(text=response)

async def bingAI(user_id, messageText):
    rsp = await EDGES[user_id]["bot"].ask(prompt=messageText, conversation_style=EDGES[user_id]["style"])
    rsp_json = json.dumps(rsp, ensure_ascii=False)
    logger.info(f"BingAI raw response: {rsp_json}")

    response, msg_suggest = process_message_main(rsp, user_id)
    return response, msg_suggest

async def bingAIStream(user_id, messageText):
    last_time = time.time() - 1.5 # 第一次间隔调小(有需要自行根据 EDGES[user_id]["interval"] 调整)
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
    bot_message = rsp_obj["item"]["messages"][1]
    msg_main, msg_ref, msg_suggest = process_message_body(bot_message, user_id)
    throttlingMax = rsp_obj["item"]["throttling"]["maxNumUserMessagesInConversation"]
    throttlingUser = rsp_obj["item"]["throttling"]["numUserMessagesInConversation"]
    msg_throttling = f"Messages: {throttlingUser}/{throttlingMax}"
    if throttlingUser >= throttlingMax:
        asyncio.run(EDGES[user_id]["bot"].reset())
        msg_throttling += "\nNote: Conversation is over, and I auto reset it successfully."
    if msg_main == "":
        response = "Something wrong. Please /reset chat" # default response
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


pyro.run()
