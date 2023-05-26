FROM python:3.11-alpine

WORKDIR /PyroEdgeGptBot

COPY . /PyroEdgeGptBot

ENV API_ID=YOUR_API_ID \
    API_KEY=YOUR_API_HASH \
    BOT_TOKEN=YOUR_BOT_TOKEN \
    ALLOWED_USER_IDS="*" \
    SUPER_USER_IDS=112113115,567568569 \
    COOKIE_BASE64="" \ 
    NOT_ALLOW_INFO="⚠️You(%user_id%) are not authorized to use this bot⚠️" \
    BOT_NAME="PyroEdgeGpt" \
    SUGGEST_MODE=callbackquery \
    DEFAULT_CONVERSATION_STYLE_TYPE=creative \
    RESPONSE_TYPE=stream \
    STREAM_INTERVAL=2 \
    LOG_LEVEL=WARNING \
    LOG_TIMEZONE=Asia/Shanghai

RUN apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev git \
    && pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

CMD [ "python", "PyroEdgeGptBot.py" ]
