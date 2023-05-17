FROM python:3.11-alpine

WORKDIR /PyroEdgeGptBot

COPY . /PyroEdgeGptBot

ENV API_ID=YOUR_API_ID \
    API_KEY=YOUR_API_HASH \
    BOT_TOKEN=YOUR_BOT_TOKEN \
    ALLOWED_USER_IDS=USER_IDS \
    COOKIE_BASE64=BASE64_ENCODED_COOKIE \
    NOT_ALLOW_INFO="⚠️You(%user_id%) are not authorized to use this bot⚠️" \
    BOT_NAME="PyroEdgeGpt" \
    SUGGEST_MODE=callbackquery \
    DEFAULT_CONVERSATION_STYLE_TYPE=creative \
    RESPONSE_TYPE=normal \
    STREAM_INTERVAL=2 \
    LOG_LEVEL=WARNING \
    LOG_TIMEZONE=Asia/Shanghai

RUN pip install -r requirements.txt

CMD [ "python", "PyroEdgeGptBot.py" ]
