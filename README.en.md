<div align="center">

# 🤖 workbuddy-auto-signin

**A tiny script that auto-claims your daily WorkBuddy check-in credits**

Zero dependencies · Pure standard library · Cross-platform · Idempotent & safe

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3](https://img.shields.io/badge/Python-3.x-blue.svg)](https://www.python.org/)
[![No Dependencies](https://img.shields.io/badge/dependencies-0-green.svg)]()
[![Platform](https://img.shields.io/badge/platform-Win%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()
[![Stars](https://img.shields.io/github/stars/DavidLam-oss/workbuddy-auto-signin.svg)](https://github.com/DavidLam-oss/workbuddy-auto-signin)

</div>

> 🍴 **This repo is an enhanced fork of [88lin/workbuddy-auto-signin](https://github.com/88lin/workbuddy-auto-signin) (MIT).** The original zero-dependency single-file check-in script is fully preserved; on top of it we added two things: **① a macOS system dialog that reminds you to re-login when the session expires; ② a launchd timer template supporting multiple trigger times + catch-up on boot/wake, plus a documented TCC gotcha.** Still MIT; copyright belongs to 88lin, enhancements to DavidLam-oss.

> A self-contained Python script that automatically claims your **WorkBuddy** (Tencent's AI coding assistant) daily check-in credits every day. It only reads the login state on *your* machine, ships no secrets, and is safe to share.

---

## 🚀 One-click setup (recommended)

No manual config needed — just hand the repo link to an AI assistant with local execution ability (e.g. **WorkBuddy**) and let it set everything up, including the daily timer. Send it this verbatim:

```text
Set up the check-in script in this repo and schedule daily auto check-in at 21:30 + 22:30 (with catch-up on boot):
https://github.com/DavidLam-oss/workbuddy-auto-signin
```

> [!TIP]
> The one-click approach relies on the AI being able to reach your machine (run Python, read the desktop client's login state). WorkBuddy itself has this ability; a pure-cloud AI (like web ChatGPT) can't run it directly, but can walk you through the manual steps below (see 🛠️ Manual usage).

---

## ✨ Features

| | |
|:---:|---|
| 🧩 | **Zero dependencies** — pure Python standard library, no `pip install`, any Python 3 works |
| 📦 | **Single file** — fully self-contained |
| 🔁 | **Idempotent & safe** — checks status first, only claims if not yet claimed; running repeatedly never double-claims |
| 🐱 | **Growth Center** — auto-claims Buddy travel gifts, dispatches Buddy, opens blind boxes, claims task rewards |
| 🧠 | **Smart report** — one line of JSON, e.g. `Successfully claimed 100 credits (7-day streak, 700 total)` |
| 🛡️ | **Robust** — handles both "already claimed" response shapes, detects 401/403 session expiry, detects off-season |
| 🌐 | **Cross-platform** — auto-detects Windows / macOS / Linux credential files |
| 🔒 | **No secrets** — the repo contains no keys; it only reads the runner's local credentials |
| 🔔 | **🆕 Session-expiry dialog** — when credentials are missing / session expired, pops a macOS system dialog reminding you to re-login (6-hour cooldown, no spam) |

### 🆕 What's new vs. the original

- **🔔 Session-expiry dialog**: the original only wrote `NO_SESSION` to the log; this fork uses `osascript display alert` to pop a **modal dialog** (always appears in the foreground, no Notification Center permission needed) telling you clearly "please re-login to the WorkBuddy desktop client". Same type only pops once per 6 hours.
- **🍎 launchd timer template**: ships `com.workbuddy.auto-signin.plist.example` with multiple daily times + `RunAtLoad` (catch-up on boot/login) + auto catch-up after sleep-wake. More reliable than an in-app WorkBuddy automation — doesn't depend on WorkBuddy running at the time.
- **📝 TCC gotcha documented**: records that a launchd background process reading `~/Documents` is blocked by macOS privacy protection (`Operation not permitted`), with the workaround of placing it under `~/Library/Application Support/`.

---

## ⚙️ How it works

After login, the WorkBuddy desktop client writes a plaintext JSON session file `workbuddy-desktop.info` (containing `accessToken`). The script flow:

1. 📂 **Locate** the credential file (auto-detected, or override with `WORKBUDDY_AUTH_FILE`)
2. 🔍 **Query** `POST /v2/billing/meter/checkin-activity-status` — claimed today?
3. 🎁 **Claim** if not yet claimed, `POST /v2/billing/meter/daily-checkin`
4. 🔔 **Remind** if credentials missing / HTTP 401·403, pop a system dialog (see 🆕 above)
5. 📤 **Output** one line of JSON, the `report` field is a human-readable summary

> [!NOTE]
> All requests hit the same endpoint the official client uses (`https://copilot.tencent.com`). The check-in endpoint was reverse-engineered from the desktop client's `app.asar` and is for personal automation only.

---

## 📋 Prerequisites

- ✅ Have installed and **logged into the WorkBuddy desktop client** at least once (it writes the credential file on login)
- ✅ **Python 3** on your machine (any version, no third-party packages needed)
- ✅ macOS users who want the dialog reminder: the system must allow the script to call AppleScript (see 🔔 Session-expiry dialog)

---

## 🛠️ Manual usage

```bash
git clone https://github.com/DavidLam-oss/workbuddy-auto-signin.git
cd workbuddy-auto-signin
python signin.py auto
```

```
python signin.py auto     # daily automation: check-in + growth center (travel gift / dispatch Buddy / blind box / task rewards)
python signin.py growth   # growth center only (no check-in)
python signin.py status   # check-in status only (debug)
python signin.py claim    # claim only (debug, idempotent)
python signin.py all      # status + claim (debug)
```

If you see `今日已签过` / `Already claimed` or `成功领取 N 积分` / `Successfully claimed N credits`, it's working.

---

## ⏰ Daily timer (macOS launchd, recommended)

The most reliable option is macOS's native **launchd** user agent: it doesn't depend on WorkBuddy being open, and natively supports catch-up on boot/wake.

1. Copy `com.workbuddy.auto-signin.plist.example` to `~/Library/LaunchAgents/com.workbuddy.auto-signin.plist`, and replace `/PATH/TO/workbuddy-auto-signin` inside with your real absolute script directory path.
   > ⚠️ **Do NOT put it under `~/Documents` / `~/Desktop` / `~/Downloads`** — macOS privacy protection (TCC) blocks background processes from reading those directories and throws `Operation not permitted`. Recommended location: `~/Library/Application Support/workbuddy-auto-signin/`.
2. Load it in Terminal (re-run this line whenever you edit the plist):
   ```bash
   launchctl bootout gui/$(id -u)/com.workbuddy.auto-signin 2>/dev/null; \
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.workbuddy.auto-signin.plist
   ```
3. Manually trigger once to verify:
   ```bash
   launchctl kickstart gui/$(id -u)/com.workbuddy.auto-signin
   tail -5 /tmp/workbuddy-auto-signin.out
   ```

**Behavior**:
- `StartCalendarInterval`: fires once each at **21:30 and 22:30** daily (the array can be extended or times changed).
- `RunAtLoad`: runs once on every boot / login = **catch-up claim**.
- **Sleep catch-up**: if the Mac is asleep at the scheduled time, launchd auto-runs the missed slot on wake; the script is idempotent, so multiple catch-up runs claim only once.
- **Not covered**: if the machine stays off all day and is never booted that day, that day is missed; but as long as you boot/login once that day, `RunAtLoad` guarantees one run as a fallback.

---

## ⏰ Daily timer (WorkBuddy in-app automation, alternative)

If you prefer "report to me in natural language via WorkBuddy", use a WorkBuddy scheduled automation. This script depends on the local desktop client's login state, so cloud CI (e.g. GitHub Actions) can't run it.

1. Place `signin.py` at a fixed location
2. Create a WorkBuddy automation:
   - **Name**: Daily WorkBuddy credit auto-claim
   - **Schedule**: daily 21:30 (add 22:30 as fallback if you like)
   - **Prompt**:
     ```text
     Run python "<absolute path to signin.py>" auto,
     and report the content of the "report" field from the command's JSON output in one sentence.
     If the report contains "claim failed" or "session expired", remind me to re-login to the WorkBuddy desktop client.
     ```

> [!NOTE]
> The in-app automation depends on WorkBuddy running at the time; the launchd approach does not, so it's more recommended.

---

## 🔔 Session-expiry dialog (🆕)

When credentials are missing (`NO_AUTH`) or the session expired (`NO_SESSION`, HTTP 401/403 / invalid local session), the script pops a modal dialog via `osascript display alert` reminding you to re-login. **A modal dialog always appears in the foreground** and is far less likely to be missed than a Notification Center banner.

> [!WARNING]
> **Why `display alert` instead of `display notification`?** An earlier version used `display notification` (via the macOS Notification Center), but when a **background / non-frontmost process** (e.g. `python3` launched directly by launchd) posts a notification, the Notification Center **silently drops it** — no error, no display, even from a foreground Terminal. In practice, switching to `display alert` (a modal dialog that hits the foreground GUI session directly, without depending on Notification Center permissions) made it pop reliably. So this version defaults to `display alert`, falling back to `display notification` only if that fails.

- **Cooldown**: same-type reminder pops at most once per 6 hours (state stored in `.notify_state.json` beside the script), avoiding spam across the 21:30 / 22:30 / wake-catch-up runs.
- **Fail-safe**: if the dialog fails, the main flow is unaffected (check-in proceeds normally, failure info still goes to the log).
- **Test the dialog**:
  ```bash
  # Trigger the NO_AUTH reminder with a non-existent credential path (safe, doesn't touch real credentials)
  WORKBUDDY_AUTH_FILE=/tmp/nope python3 /PATH/TO/workbuddy-auto-signin/signin.py auto
  # If it was already popped within 6h and got cooldowned, clear state first then test:
  rm -f /PATH/TO/workbuddy-auto-signin/.notify_state.json
  ```

---

## 🔧 Configuration

| Environment variable | Purpose |
|---|---|
| `WORKBUDDY_AUTH_FILE` | Manually specify the credential file path when auto-detection fails |

---

## 🧪 Troubleshooting

| Symptom | Fix |
|---|---|
| `NO_AUTH / credential not found` | Log into the WorkBuddy desktop client once; or set `WORKBUDDY_AUTH_FILE` |
| `NO_SESSION / HTTP 401\|403` | Session expired — re-login to the desktop client, automation recovers automatically; this fork pops a dialog |
| `INACTIVE / check-in not open` | Off-season, normal, no action needed |
| `Operation not permitted` (launchd background) | Script is under `~/Documents` etc. (TCC protected) — move it under `~/Library/Application Support/` and re-run bootstrap |
| Dialog doesn't appear | First rule out the 6h cooldown (run `rm .notify_state.json` then test); this version defaults to `display alert` (modal dialog, reliably foreground) — if even `display alert` won't show, it's usually an extreme TCC/accessibility restriction, see 🔔 above |
| Inspect raw response | `python signin.py status` or `python signin.py all` |

> [!IMPORTANT]
> On session expiry the script returns `NO_SESSION` explicitly and pops a dialog reminding you to re-login to the desktop client; after re-login the automation recovers with no changes needed.

---

## 🔐 Security & privacy

- The script only reads **your own local** WorkBuddy session file; it contains, embeds, or transmits no third-party secrets
- It never prints `accessToken`; the `Authorization` header never appears in logs
- Safe to fork, share, and run on your own machine — it only acts on **your own** login state

---

## ⚠️ Disclaimer

> [!WARNING]
> This is an **unofficial** tool with no affiliation to Tencent or WorkBuddy. The check-in endpoint was reverse-engineered from the desktop client's `app.asar`. Use at your own risk; the endpoint may change at any time without notice. Please comply with the relevant terms of service.

---

## 📄 License

[MIT](LICENSE) © 2026 [88lin](https://github.com/88lin/workbuddy-auto-signin) (original); enhancements in this repo © 2026 DavidLam-oss.
