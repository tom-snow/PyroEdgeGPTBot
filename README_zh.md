<div align="center">

# PyroEdgeGPTBot
_在 Telegram 上使用 Bing AI ( 使用 [EdgeGPT](https://github.com/acheong08/EdgeGPT) API )_

<a href="./README.md">English</a> -
<a>中文</a>

</div>

# 安装
## 依赖
* python 3.8+
* 拥有访问 http://bing.com/chat 权限的 Microsoft 账号
* 来自 [https://my.telegram.org/apps](https://my.telegram.org/apps) 的 Telegram API_ID 和 API_KEY
* 来自 [@botfather](https://t.me/botfather) 的 Telegram BOT_TOKEN
* 较好的动手能力和清晰的头脑！


<details>
  <summary>

### 检查 bing AI 资格 (必须)

  </summary>

- 安装最新版本 Microsoft Edge
- 或者，你可以使用任何浏览器，并将用户代理设置为看起来像你正在使用 Edge。你可以使用像 “User-Agent Switcher and Manager” 这样的扩展轻松实现这一点， [Chrome](https://chrome.google.com/webstore/detail/user-agent-switcher-and-m/bhchdcejhohfmigjafbampogmaanbfkg) 与 [Firefox](https://addons.mozilla.org/en-US/firefox/addon/user-agent-string-switcher/) 插件地址.
- 打开 [bing.com/chat](https://bing.com/chat)
- 如果你看到了“聊天”，说明你具备资格

</details>



<details>
  <summary>

### 获取 cookie (必须)

  </summary>

- 安装 cookie editor 插件，[Chrome](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm) , [Firefox](https://addons.mozilla.org/en-US/firefox/addon/cookie-editor/) 与 [Edge](https://microsoftedge.microsoft.com/addons/detail/cookieeditor/neaplmfkghagebokkhpjpoebhdledlfi) 商店地址
- 前往 [`bing.com`](https://bing.com/)
- 打开插件
- 点击右下角 "Export", 然后点 "Export as JSON" (这将把 cookies 复制到剪贴板)
- 将你的 cookies 粘贴到 `cookies.json`

</details>


## 安装 python 依赖
```shell
pip install -r requirements.txt
```

## 设置环境变量
```shell
cp .env.example .env
```
然后修改 `.env` 文件并且设置好 `API_ID`, `API_KEY`, `BOT_TOKEN` 和 `ALLOWED_USER_IDS` 的值。或者你可以在终端设置环境变量:
```shell
export API_ID='1234567'
export API_KEY='abcdefg2hijk5lmnopq8rstuvwxyz9'
export BOT_TOKEN='123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11'
export ALLOWED_USER_IDS='112113115,567568569'
```

# 运行脚本
```shell
python PyroEdgeGptBot.py
```


<details>
  <summary>

## (可选)设置机器人命令

  </summary>

- 联系 [@botfather](https://t.me/botfather)
- 发送命令 `/mybots` 然后选择你的机器人再点击 `Edit Bot` -> `Edit Commands`
- 复制粘贴底下内容再发送.
```
start - 开始
help - 帮助
reset - 重置
new - 新会话
switch - 切换聊天模式
interval - 设置修改消息间隔
suggest_mode - 建议消息模式
```

</details>

