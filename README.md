<div align="center">

# 🤖 workbuddy-auto-signin

**自动领取 WorkBuddy 每日签到积分的小脚本**

零依赖 · 纯标准库 · 跨平台 · 幂等安全

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3](https://img.shields.io/badge/Python-3.x-blue.svg)](https://www.python.org/)
[![No Dependencies](https://img.shields.io/badge/dependencies-0-green.svg)]()
[![Platform](https://img.shields.io/badge/platform-Win%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()
[![Stars](https://img.shields.io/github/stars/DavidLam-oss/workbuddy-auto-signin.svg)](https://github.com/DavidLam-oss/workbuddy-auto-signin)

</div>

> 🌐 **English documentation**: [README.en.md](README.en.md)

> 🍴 **本仓库是 [88lin/workbuddy-auto-signin](https://github.com/88lin/workbuddy-auto-signin) (MIT) 的增强 fork**，原仓库的零依赖单文件签到脚本完全保留，我们在此基础上补了两件事：**① 登录态失效时弹 macOS 系统对话框提醒你重新登录；② 附一份 launchd 定时模板，支持多时间点 + 开机/唤醒补领，并记录了一个 TCC 踩坑。** 协议仍为 MIT，版权归 88lin，增强部分归 DavidLam-oss。

> 一个自包含的 Python 脚本，每天自动帮你领取 **WorkBuddy**（腾讯 AI 编程助手）的每日签到积分。只读取你自己机器上的登录态，零内置密钥，可安全分享。

---

## 🚀 一键使用（推荐）

不用手动配置——直接把仓库链接发给有本地执行能力的 AI 助手（如 **WorkBuddy**），让它帮你跑起来并设置每日定时签到。把下面这段原样发过去即可：

```text
帮我把这个仓库的签到脚本跑起来，并设置每天 21:30 + 22:30 自动签到（含开机补领）：
https://github.com/DavidLam-oss/workbuddy-auto-signin
```

> [!TIP]
> 一键方式依赖 AI 能访问你本机（运行 Python、读取桌面端登录态）。WorkBuddy 自身就具备这个能力；纯云端 AI（如网页版 ChatGPT）无法直接执行，但可指导你手动操作（见下方 🛠️ 手动使用）。

---

## ✨ 特性

| | |
|:---:|---|
| 🧩 | **零依赖** — 纯 Python 标准库，不用 `pip install`，任意 Python 3 即可 |
| 📦 | **单文件** — 完全自包含 |
| 🔁 | **幂等安全** — 先查状态，未签才领；重复运行不会多领 |
| 🐱 | **成长中心** — 自动领 Buddy 旅行礼物、派 Buddy 出发、开盲盒、领任务奖励 |
| 🧠 | **智能汇报** — 一行 JSON，如 `成功领取 100 积分（连续 7 天，累计 700 积分）` |
| 🛡️ | **健壮** — 兼容"已签"两种返回形态、识别 401/403 登录态过期、识别非签到季 |
| 🌐 | **跨平台** — 自动探测 Windows / macOS / Linux 凭据文件 |
| 🔒 | **无密钥** — 仓库不含任何密钥，只读取运行者本机登录凭据 |
| 🔔 | **🆕 失效弹窗提醒** — 凭据缺失 / 登录态失效时，弹 macOS 系统对话框提醒你重新登录（6 小时去抖，不刷屏） |

### 🆕 相比原版新增

- **🔔 失效弹窗提醒**：原版只在日志里写 `NO_SESSION`；本版用 `osascript display alert` 弹一个**模态对话框**（必然出现在前台，不依赖通知中心权限），明确告诉你"请重新登录 WorkBuddy 桌面端"。同类型 6 小时内只弹一次。
- **🍎 launchd 定时模板**：提供 `com.workbuddy.auto-signin.plist.example`，每天多个时间点 + `RunAtLoad`（开机/登录补领）+ 沉睡唤醒后自动补跑。比 WorkBuddy 应用内自动化更稳——不依赖 WorkBuddy 当时在运行。
- **📝 TCC 踩坑文档**：记录了 launchd 后台进程读取 `~/Documents` 会被 macOS 隐私保护拦截（`Operation not permitted`）的现象，并给出"放到 `~/Library/Application Support/`"的绕过方法。

---

## ⚙️ 工作原理

登录后，WorkBuddy 桌面端写出明文 JSON 会话文件 `workbuddy-desktop.info`（含 `accessToken`）。脚本流程：

1. 📂 **定位**凭据文件（自动探测，或用 `WORKBUDDY_AUTH_FILE` 覆盖）
2. 🔍 **查询** `POST /v2/billing/meter/checkin-activity-status` — 今天是否已领？
3. 🎁 **领取** 若未领，`POST /v2/billing/meter/daily-checkin`
4. 🔔 **提醒** 若凭据缺失 / 接口 401·403，弹系统对话框（见上方 🆕）
5. 📤 **输出** 一行 JSON，`report` 字段是人话汇报

> [!NOTE]
> 所有请求都打到官方客户端用的同一个 endpoint（`https://copilot.tencent.com`）。签到接口系从桌面端 `app.asar` 逆向得到，仅供个人自动化使用。

---

## 📋 前置条件

- ✅ 已安装并**登录过 WorkBuddy 桌面端**（登录后自动写出凭据文件）
- ✅ 本机有 **Python 3**（任意版本，无需任何第三方包）
- ✅ macOS 用户如要弹窗提醒：系统需允许脚本调用 AppleScript（见 🔔 失效弹窗提醒 说明）

---

## 🛠️ 手动使用

```bash
git clone https://github.com/DavidLam-oss/workbuddy-auto-signin.git
cd workbuddy-auto-signin
python signin.py auto
```

```
python signin.py auto     # 每日自动化：签到 + 成长中心（领旅行礼物/派Buddy/开盲盒/领任务奖）
python signin.py growth   # 仅成长中心（不签到）
python signin.py status   # 仅查签到状态（调试）
python signin.py claim    # 仅领取签到（调试，幂等）
python signin.py all      # 查签到状态 + 领取（调试）
```

看到 `今日已签过` 或 `成功领取 N 积分` 就说明通了。

---

## ⏰ 每日定时（macOS launchd，推荐）

最稳的方案是 macOS 原生的 **launchd** 用户代理：不依赖 WorkBuddy 是否开着，且原生支持开机/唤醒补领。

1. 把 `com.workbuddy.auto-signin.plist.example` 复制为 `~/Library/LaunchAgents/com.workbuddy.auto-signin.plist`，把里面的 `/PATH/TO/workbuddy-auto-signin` 改成你真实的脚本目录绝对路径。
   > ⚠️ **不要放在 `~/Documents` / `~/Desktop` / `~/Downloads` 下**——macOS 隐私保护(TCC)会拦截后台进程读取这些目录，报 `Operation not permitted`。推荐放在 `~/Library/Application Support/workbuddy-auto-signin/`。
2. 终端加载（改完 plist 后都重跑一次这行）：
   ```bash
   launchctl bootout gui/$(id -u)/com.workbuddy.auto-signin 2>/dev/null; \
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.workbuddy.auto-signin.plist
   ```
3. 立即手动触发一次验证：
   ```bash
   launchctl kickstart gui/$(id -u)/com.workbuddy.auto-signin
   tail -5 /tmp/workbuddy-auto-signin.out
   ```

**行为说明**：
- `StartCalendarInterval`：每天 **21:30 与 22:30** 各触发一次（数组可增减、可改时间）。
- `RunAtLoad`：每次开机 / 登录立即跑一次 = **补领**。
- **沉睡补领**：若 Mac 在计划时间处于睡眠，launchd 在唤醒后自动补跑错过的点；脚本幂等，补跑多次也只领一次。
- **不覆盖的情况**：整天空机且当天完全不开机，那天会漏签；但只要当天任意一次开机/登录，`RunAtLoad` 必跑一次兜底。

---

## ⏰ 每日定时（WorkBuddy 应用内自动化，备选）

若你更想要"用 WorkBuddy 自然语言汇报给我"的形式，可用 WorkBuddy 定时自动化。本脚本依赖本机桌面端登录态，云端 CI（如 GitHub Actions）跑不了。

1. 把 `signin.py` 放到固定位置
2. 新建 WorkBuddy 自动化：
   - **名称**：每日自动领 WorkBuddy 积分
   - **计划**：每天 21:30（可加 22:30 兜底）
   - **提示词**：
     ```text
     运行 python "<signin.py 绝对路径>" auto，
     把命令输出的 JSON 里 report 字段的内容，直接一句话汇报给我。
     若 report 含"领取失败"或"登录态已失效"，提醒我重新登录 WorkBuddy 桌面端。
     ```

> [!NOTE]
> 应用内自动化依赖 WorkBuddy 当时在运行；launchd 方案不依赖，故更推荐。

---

## 🔔 失效弹窗提醒（🆕）

凭据缺失（`NO_AUTH`）或登录态失效（`NO_SESSION`，接口 401/403 / 本地会话无效）时，脚本通过 `osascript display alert` 弹一个模态对话框提醒你重新登录。**模态对话框必然出现在前台**，比通知中心通知更不会被漏看。

> [!WARNING]
> **为什么用 `display alert` 而不是 `display notification`？** 早期版本用 `display notification`（走 macOS 通知中心），但当一个**后台/非前台 App 进程**（如 launchd 直起的 `python3`）发通知时，通知中心会把它**静默丢弃**——不报错、也不显示，前台终端跑也一样。实测改成 `display alert`（模态对话框，直接命中前台 GUI 会话，不依赖通知中心权限）后稳定弹出。所以本版默认 `display alert`，仅在其失败时退化回 `display notification`。

- **去抖**：同类型提醒 6 小时内只弹一次（状态记在脚本同目录的 `.notify_state.json`），避免 21:30/22:30/唤醒补跑多次狂弹。
- **安全失败**：弹窗失败不影响主流程（签到照常进行，失败信息照常写日志）。
- **测试弹窗**：
  ```bash
  # 用不存在的凭据路径触发 NO_AUTH 提醒（安全，不动真凭据）
  WORKBUDDY_AUTH_FILE=/tmp/nope python3 /PATH/TO/workbuddy-auto-signin/signin.py auto
  # 若 6 小时内已弹过被去抖，先清状态再测：
  rm -f /PATH/TO/workbuddy-auto-signin/.notify_state.json
  ```

---

## 🔧 配置

| 环境变量 | 作用 |
|---|---|
| `WORKBUDDY_AUTH_FILE` | 自动探测失败时，手动指定凭据文件路径 |

---

## 🧪 排错

| 现象 | 处理 |
|---|---|
| `NO_AUTH / 未找到登录凭据` | 先登录一次 WorkBuddy 桌面端；或设置 `WORKBUDDY_AUTH_FILE` |
| `NO_SESSION / HTTP 401\|403` | 登录态过期——重新登录桌面端，自动化自动恢复；本版会弹窗提醒 |
| `INACTIVE / 签到活动未开启` | 非签到季，属正常，无需处理 |
| `Operation not permitted`（launchd 后台） | 脚本放在了 `~/Documents` 等 TCC 保护区——移到 `~/Library/Application Support/` 下，重跑 bootstrap |
| 弹窗不出现 | 先确认不是 6h 去抖（先 `rm .notify_state.json` 再测）；本版默认 `display alert`（模态对话框，稳定弹前台），若连 `display alert` 都不弹，多为极端 TCC/辅助功能限制，见上方 🔔 说明 |
| 调试原始返回 | `python signin.py status` 或 `python signin.py all` |

> [!IMPORTANT]
> 登录态失效时脚本会明确返回 `NO_SESSION` 并弹窗提醒重新登录桌面端；重新登录后自动化无需任何改动即自动恢复。

---

## 🔐 安全与隐私

- 脚本只读取**你自己本机**的 WorkBuddy 会话文件，不含、不内嵌、不传输任何第三方密钥
- 永远不会打印 `accessToken`，`Authorization` 头不会出现在日志里
- 可安全 fork、分享、在自己机器上运行——它只作用于**你自己的**登录态

---

## ⚠️ 免责声明

> [!WARNING]
> 本项目为**非官方**工具，与腾讯或 WorkBuddy 无任何隶属关系。签到接口系从桌面端 `app.asar` 逆向得到。使用风险自负；接口可能随时变动且不另行通知。请遵守相关服务条款。

---

## 📄 协议

[MIT](LICENSE) © 2026 [88lin](https://github.com/88lin/workbuddy-auto-signin)（原版）；本仓库增强部分 © 2026 DavidLam-oss。
