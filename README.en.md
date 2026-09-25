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

> 🍴 **This repo is an enhanced fork of [88lin/workbuddy-auto-signin](https://github.com/88lin/workbuddy-auto-signin) (MIT).** The original zero-dependency single-file check-in script is fully preserved; on top of it we added several things: **① a macOS system dialog that reminds you to re-login when the session expires; ② a launchd timer template supporting multiple trigger times + catch-up on boot/wake, plus a documented TCC gotcha; ③ automatic streak-tier redemption in the Growth Center; ④ network fault tolerance so a transient network blip never spams your logs with tracebacks; ⑤ decryption of the desktop client 5.3.x+ at-rest encrypted credentials.** Still MIT; copyright belongs to 88lin, enhancements to DavidLam-oss.

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
| 🎁 | **🆕 Streak tier redemption** — auto-redeems the 7 / 14 / 28-day streak tiers (14 days → 50 credits, 28 days → 150 credits) |
| 🧠 | **Smart report** — one line of JSON, e.g. `Successfully claimed 100 credits (7-day streak, 700 total)` |
| 🛡️ | **Robust** — handles both "already claimed" response shapes, detects 401/403 session expiry, detects off-season |
| 🌐 | **Cross-platform** — auto-detects Windows / macOS / Linux credential files |
| 🔒 | **No secrets** — the repo contains no keys; it only reads the runner's local credentials |
| 🔔 | **🆕 Session-expiry dialog** — when credentials are missing / session expired, pops a macOS system dialog reminding you to re-login (6-hour cooldown, no spam) |
| 🌐 | **🆕 Network fault tolerance** — on a network blip (e.g. Wi-Fi not ready right after wake), retries once; if still down, prints a clean JSON + exit code 3 instead of dumping a traceback; the 30-min timer retries automatically |
| 🔐 | **🆕 Encrypted credential decryption** — automatically decrypts the at-rest encrypted credentials (`$wbEncrypted`) of desktop client 5.3.x+; tokens never touch disk or logs |

### 🆕 What's new vs. the original

- **🔔 Session-expiry dialog**: the original only wrote `NO_SESSION` to the log; this fork uses `osascript display alert` to pop a **modal dialog** (always appears in the foreground, no Notification Center permission needed) telling you clearly "please re-login to the WorkBuddy desktop client". Same type only pops once per 6 hours.
- **🍎 launchd timer template**: ships `com.workbuddy.auto-signin.plist.example` with multiple daily times + `RunAtLoad` (catch-up on boot/login) + auto catch-up after sleep-wake. More reliable than an in-app WorkBuddy automation — doesn't depend on WorkBuddy running at the time.
- **📝 TCC gotcha documented**: records that a launchd background process reading `~/Documents` is blocked by macOS privacy protection (`Operation not permitted`), with the workaround of placing it under `~/Library/Application Support/`.
- **🎁 Streak tier redemption**: the original only queries `/streak` status and **never redeems**. This fork auto-calls the redemption endpoint when a tier unlocks — see the dedicated chapter below.
- **🔐 Encrypted credential decryption**: supports the desktop client 5.3.x+ at-rest credential encryption (see the dedicated chapter below).

---

### 🎁 Streak tier redemption (🆕)

The Growth Center's streak has three reward tiers at **7 / 14 / 28 days**, and they **must be manually redeemed** — they expire if you don't claim them:

| Tier | Credits | Energy | Make-up card | Blind-box chance |
|:---:|:---:|:---:|:---:|:---:|
| 7-day streak | — | +2 | +1 | +1 |
| 14-day streak | **+50** | +3 | +1 | +1 |
| 28-day streak | **+150** | +5 | +1 | +1 |

Every run reads `POST /v2/activity/growth/streak`'s `redemption_status` and **only redeems a tier when its status is "unlocked and not yet claimed"** — `locked` / `claimed` are always skipped. A redemption failure is only written to the report and never blocks the check-in you already completed.

> **⚠️ About the endpoint: located, but the payload is inferred**
>
> The redemption endpoint `POST /v2/activity/growth/redeem` was **confirmed to exist by actual probing** (not a 404; it returns a structured error). The request body `{"tier": <days int>}` is based on:
> - passing `tier` as a string → `invalid redemption request` (JSON binding failure, proving the field is an int)
> - passing `tier` as any integer → uniformly `invalid request` (`-1`/`0`/`1`/`7`/`14`/`28`/`100` all identical, **no enum validation**, meaning the rejection happens at a unified business layer = tier not yet unlocked)
>
> Because the probing account only had a 5-day streak at the time (below the 7-day threshold), **a real redemption has not yet been tested in an "unlocked" state**. If your log first shows `兑换 7d 档失败（HTTP 400 invalid request）` when you reach the 7-day tier, it means the payload needs more fields — paste that log line and we'll keep calibrating.

### 🔐 Encrypted credential decryption (🆕)

Starting with desktop client **5.3.x**, WorkBuddy stores sensitive fields in `workbuddy-desktop.info` **encrypted at rest** (`{"$wbEncrypted":1,"envelope":"..."}`, AES-256-GCM). The original script reads the plaintext field, gets the ciphertext, and sends it as a Bearer token — the server replies 401 and every check-in fails.

This fork's adaptation (`wbcred.js` + `signin.py` working together):

1. `signin.py` detects `$wbEncrypted` fields in the credential file and automatically invokes the decryption helper `wbcred.js`;
2. `wbcred.js` runs under the **WorkBuddy app's own Electron binary** with `ELECTRON_RUN_AS_NODE=1` — the decryption key is fetched **at runtime** from the native binding inside the client's Framework (`electron_browser_workbuddy_storage`); it never touches disk or config files;
3. The helper returns the decrypted session as a single-line JSON to `signin.py`; everything else (check-in / Growth Center / redemption / reporting) is unchanged.

**Notes**:

- The WorkBuddy client must be installed at the standard path (`/Applications/WorkBuddy.app`); for custom locations, set `WORKBUDDY_ELECTRON_BIN` to the binary path.
- **Key rotation requires no action** — the key is fetched fresh on every run and follows the client automatically.
- If the client isn't running / the key is unavailable, the script falls back to the `NO_SESSION` flow (including the dialog reminder) — no crash, no dirty logs.

---

## 🧭 Troubleshooting guide when the client changes (lessons learned)

When a client upgrade breaks the script again, follow this path ( distilled from the 2026-09 5.3.x encryption incident):

1. **Classify the symptom first**: all logs are `HTTP 401` and the credential file was recently rewritten by the client → the credential storage likely changed. Look for a `$wbEncrypted` marker and a file-size jump (3.4KB → 7.2KB = encrypted). If the token is far from expiry (`expiresAt`) yet you get 401, it's a local read problem, not a login problem.
2. **The key only lives inside the client binary**: neither shallow disk paths nor the Keychain will hold it in plaintext. The fastest extraction channel is WorkBuddy's own Electron binary:
   ```bash
   ELECTRON_RUN_AS_NODE=1 /Applications/WorkBuddy.app/Contents/MacOS/Electron -e \
     "console.log(process._linkedBinding('electron_browser_workbuddy_storage').loggerGet())"
   ```
   If the binding name changed, grep the asar / Framework binary for `electron_browser_*_storage`.
3. **Watch the runtime-mode trap**: when invoking the Electron binary from a terminal/script, the environment may already carry `ELECTRON_RUN_AS_NODE=1` (e.g. inside a WorkBuddy session shell) — unset it first; without the variable it launches the real app and hits the single-instance lock.
4. **Crypto details quick reference** (`packages/at-rest-crypto`, suite 1 / sym-v1): AES-256-GCM, 12-byte nonce, 16-byte authTag; AAD = `"WB-AAD\0"` + `[1]` + lenPref(`WBEV1`) + lenPref(`sym-v1`) + uint32(suite) + lenPref(keyId) + framing code (field=2) + sequence/final markers. **Do not pre-validate keyId** — the derived keyId may differ from the envelope's while the key is still correct; trust the authTag check. Field plaintexts may be raw strings (e.g. JWTs) — fall back to returning the raw string when `JSON.parse` fails.
5. **Reverse-engineering entry points**: grep `at-rest-crypto` / `credential-protection` in `app.asar` for byte offsets, then extract context around those offsets with Python chunked reads (**grepping the full 283MB asar with a broad regex gets SIGTERMed**).
6. **Don't take the modified-bundle detour**: `codesign --deep` re-signing of a copied bundle drops entitlements (`allow-jit` etc.) and Electron exits silently; signed apps also ignore an argv app-directory path.
7. **Verify before shipping**: run `signin.py auto` once and check the JSON report, then wait one launchd cycle to confirm the log recovers.

---

## ⚙️ How it works

After login, the WorkBuddy desktop client writes a JSON session file `workbuddy-desktop.info` (containing `accessToken`; encrypted at rest on 5.3.x+, which this fork decrypts automatically — see the chapter above). The script flow:

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
- `StartInterval`: self-checks every **30 minutes**; fires whenever the Mac is awake. Combined with the script's idempotency, this guarantees "if you booted or woke the Mac at all today, it claims" — this is what makes "auto-claim on opening the lid in the morning" work, because `RunAtLoad` **only runs on boot/login, NOT on a plain sleep→wake**.
- `RunAtLoad`: runs once on every boot / login = **catch-up claim**.
- **Sleep catch-up (limited)**: if the Mac is asleep at 21:30/22:30, launchd catches up those missed slots on wake; but when you open the lid in the morning, today's slots are still in the future with nothing to catch up, so wake alone won't claim — that gap is covered by `StartInterval` above.
- **Not covered**: if the machine stays off all day and is never booted that day, that day is missed; but as long as you boot/login once that day, or wake and stay awake ≥30 min, `StartInterval` guarantees one run as a fallback.

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
