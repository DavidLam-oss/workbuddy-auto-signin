"""WorkBuddy 每日签到自动领取脚本。

读取本机 WorkBuddy 桌面端的登录会话，调用其签到接口自动领取每日积分：
  POST {endpoint}/v2/billing/meter/checkin-activity-status  查询签到状态
  POST {endpoint}/v2/billing/meter/daily-checkin            领取今日积分

响应契约：
  - 领取成功 : 含 credit 字段，如 {"credit": 100}
  - 今日已签 : null 或 HTTP 400 + {"code":10001,"msg":"今天已签到，请明天再来"}
               幂等，两种形态都按"已签"处理，不计失败
  - 业务错误 : {"code": ..., "msg": ...}
  - 登录失效 : HTTP 401/403，需重新登录桌面端

凭据文件由桌面端登录后自动写入；脚本按平台自动探测，或用环境变量
WORKBUDDY_AUTH_FILE 指定。任何模式下都不会打印令牌，可安全分享。

用法：
  python signin.py auto     # 每日自动化：签到 + 成长中心（领旅行礼物/派Buddy/开盲盒/领任务奖）
  python signin.py growth   # 仅成长中心（不签到）
  python signin.py status   # 仅查签到状态（调试）
  python signin.py claim    # 仅领取签到（调试，幂等）
  python signin.py all      # 查签到状态 + 领取（调试）
"""

import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

DEFAULT_ENDPOINT = "https://copilot.tencent.com"
AUTH_BASENAME = os.path.join("CodeBuddyExtension", "Data", "Public", "auth", "workbuddy-desktop.info")


def find_auth_file():
    """按平台探测 WorkBuddy 桌面端写出的登录凭据文件，支持环境变量覆盖。"""
    override = os.environ.get("WORKBUDDY_AUTH_FILE")
    if override:
        return override
    home = os.path.expanduser("~")
    local = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
    candidates = [
        os.path.join(local, AUTH_BASENAME),                                  # Windows
        os.path.join(home, "Library", "Application Support", AUTH_BASENAME),  # macOS
        os.path.join(home, ".config", AUTH_BASENAME),                        # Linux
        os.path.join(home, ".workbuddy", "auth", "workbuddy-desktop.info"),  # 兜底
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def load_session(auth_file):
    with open(auth_file, "r", encoding="utf-8") as f:
        return json.load(f)


def build_headers(session):
    auth = session.get("auth") or {}
    account = session.get("account") or {}
    token = auth.get("accessToken")
    uid = account.get("uid")
    if not token or not uid:
        raise SystemExit("NO_SESSION: 本地未找到有效登录会话")
    headers = {
        "Accept": "application/json",
        "Authorization": "Bearer %s" % token,
        "Content-Type": "application/json",
        "X-User-Id": uid,
        "User-Agent": "WorkBuddy",
    }
    if account.get("enterpriseId"):
        headers["X-Enterprise-Id"] = account["enterpriseId"]
        headers["X-Tenant-Id"] = account["enterpriseId"]
    if auth.get("domain"):
        headers["X-Domain"] = auth["domain"]
    return headers


class NetworkError(Exception):
    """网络层不可用：DNS 解析失败、连接超时、连接被重置等。

    与 HTTP 状态码错误不同（那是有响应的服务端错误），这类错误意味着请求
    根本没送达。典型场景：Mac 刚唤醒时 launchd 立刻触发本脚本，而 Wi-Fi
    尚未就绪，于是 getaddrinfo 失败。属于可自愈的瞬时故障 —— 不弹通知打扰
    用户，交给下一次定时运行重试即可。
    """


NETWORK_RETRY_DELAY = 2  # 秒：网络失败后短暂等待再重试一次


def _err_text(e):
    """把异常压成一行短文本，用于 JSON 汇报。"""
    return ((str(e) or e.__class__.__name__).strip() or e.__class__.__name__)[:120]


def _request(url, headers, method="GET", payload=None, _retry=1):
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, {"raw": raw[:500]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:500]}
    except (urllib.error.URLError, OSError) as e:
        # 网络不可达：先短暂重试一次（覆盖"唤醒瞬间网络未就绪"），
        # 仍失败则抛 NetworkError，由上层输出干净结果而不是 traceback。
        if _retry > 0:
            time.sleep(NETWORK_RETRY_DELAY)
            return _request(url, headers, method=method, payload=payload,
                            _retry=_retry - 1)
        raise NetworkError(_err_text(e))


def post(url, headers, payload=None):
    return _request(url, headers, method="POST", payload=payload)


def get(url, headers):
    return _request(url, headers, method="GET")


def dig(obj, key):
    """在可能被 data/result 包裹的响应里找字段，兼容信封结构。"""
    if isinstance(obj, dict):
        if key in obj and obj[key] is not None:
            return obj[key]
        for k in ("data", "result", "resp", "response"):
            if k in obj and isinstance(obj[k], dict):
                r = dig(obj[k], key)
                if r is not None:
                    return r
    return None


def fmt_credit(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return v


def _is_already_checked_in(cbody):
    """领取接口返回是否表示"今日已签"（兼容 null 与 400+code10001）。"""
    if cbody is None:
        return True
    if isinstance(cbody, dict):
        msg = cbody.get("msg") or ""
        if cbody.get("code") == 10001 or "已签" in msg:
            return True
    return False


def _already_report(status, via=None):
    """根据状态构造"今日已签"汇报 dict。"""
    today_credit = dig(status, "today_credit") or dig(status, "daily_credit")
    streak_days = dig(status, "streak_days")
    total_credits = dig(status, "total_credits")
    is_streak_day = dig(status, "is_streak_day")
    next_streak_day = dig(status, "next_streak_day")
    inner = []
    if today_credit is not None:
        inner.append("今日 +%s" % fmt_credit(today_credit))
    if streak_days is not None:
        inner.append("连续 %s 天" % streak_days)
    if total_credits is not None:
        inner.append("累计 %s 积分" % fmt_credit(total_credits))
    prefix = via or "今日已签过"
    report = "%s（%s）" % (prefix, "，".join(inner)) if inner else prefix
    return {
        "result": "ALREADY",
        "report": report,
        "today_credit": today_credit,
        "streak_days": streak_days,
        "total_credits": total_credits,
        "is_streak_day": is_streak_day,
        "next_streak_day": next_streak_day,
    }


NOTIFY_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".notify_state.json")
NOTIFY_COOLDOWN = 6 * 3600  # 同类型通知 6 小时内不重复弹，避免多次运行刷屏


def _load_notify_state():
    try:
        with open(NOTIFY_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_notify_state(state):
    try:
        with open(NOTIFY_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def _notify(kind, title, message):
    """弹 macOS 提醒（带去抖）。
    优先用 display alert（模态对话框，必然出现在前台，适合"请重新登录"这类不可错过提醒）；
    若 alert 失败（如后台无 UI 会话），退化为 display notification（通知中心）。
    通知失败不影响主流程。"""
    now = time.time()
    state = _load_notify_state()
    last = state.get(kind)
    if isinstance(last, (int, float)) and (now - last) < NOTIFY_COOLDOWN:
        return  # 冷却中，跳过
    try:
        # 转义反斜杠与双引号，避免 AppleScript 语法错误
        safe_msg = message.replace("\\", "\\\\").replace('"', '\\"')
        safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
        # 1) 模态对话框：必然可见，不依赖通知中心权限
        alert = 'display alert "%s" message "%s" as warning' % (safe_title, safe_msg)
        r = subprocess.run(["/usr/bin/osascript", "-e", alert],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        if r.returncode != 0:
            # 2) 退化：通知中心通知（后台/无 UI 时可能不显示，但尽量尝试）
            note = ('display notification "%s" with title "%s" subtitle '
                    '"WorkBuddy 每日签到" sound name "Glass"' % (safe_msg, safe_title))
            subprocess.run(["/usr/bin/osascript", "-e", note],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        state[kind] = now
        _save_notify_state(state)
    except Exception:
        pass


def redeem_streak_tiers(headers, endpoint, streak_body):
    """连签档位兑换：7d / 14d / 28d 三档奖励。

    端点 POST {endpoint}/v2/activity/growth/redeem，body {"tier": <天数 int>}。

    payload 结构说明（由探测推断，尚未在"档位已解锁"状态下实测）：
      - tier 传字符串  -> "invalid redemption request"（JSON 绑定失败 => 字段是 int）
      - tier 传任意整数 -> 一律 "invalid request"（无枚举校验，说明拒绝发生在
                            统一业务层，即档位未解锁）
    因此这里只在档位状态为"非 locked 且未领过"时才发请求，
    失败只记录不抛错，不影响签到主流程。
    """
    data = (streak_body or {}).get("data") or {}
    rs = data.get("redemption_status") or {}
    tiers = rs.get("tiers") or []
    if not tiers:
        return 0, []

    parts = []
    credits = 0
    for t in tiers:
        tier_key = t.get("tier")            # "7d" / "14d" / "28d"
        days = t.get("days")                # 7 / 14 / 28
        if not tier_key or not isinstance(days, int):
            continue
        status = rs.get("tier_%s_status" % tier_key)
        already = rs.get("tier_%s_count" % tier_key)
        # 只在"已解锁且未领过"时尝试；locked / claimed 直接跳过
        if status in (None, "", "locked", "claimed") or already:
            continue

        code, body = post(endpoint + "/v2/activity/growth/redeem",
                          headers, {"tier": days})
        msg = ""
        if isinstance(body, dict):
            msg = str(body.get("msg") or body.get("error_msg") or "")[:80]
        ok = (200 <= code < 300) and isinstance(body, dict) and body.get("code") == 0
        if ok:
            rc = t.get("credit") or 0
            credits += rc
            bits = ["兑换 %s 档" % tier_key]
            if rc:
                bits.append("+%s 积分" % rc)
            if t.get("energy"):
                bits.append("+能量%s" % t.get("energy"))
            if t.get("cards"):
                bits.append("+补签卡%s" % t.get("cards"))
            if t.get("chances"):
                bits.append("+盲盒机会%s" % t.get("chances"))
            parts.append("".join(bits))
        else:
            # 失败只记录，供后续校正 payload 结构
            parts.append("兑换 %s 档失败（HTTP %s %s）" % (tier_key, code, msg))
    return credits, parts


def run_growth(headers, endpoint):
    """成长中心自动化：领旅行礼物→派 Buddy 出发→开盲盒→领任务奖→汇报。"""
    base = endpoint + "/v2/activity/growth"
    parts = []
    credits_gained = 0

    # --- 1. Buddy 旅行：领礼物 + 派出发 ---
    scode, sbody = get(base + "/buddy/travel/status", headers)
    travel = dig(sbody, "state") if (200 <= scode < 300) else None

    if scode in (401, 403):
        return 1, {"result": "NO_SESSION",
                   "report": "登录态已失效，请重新登录 WorkBuddy 桌面端"}
    if travel == "arrived":
        record_id = dig(sbody, "record_id")
        reward = dig(sbody, "reward_credit") or 0
        ccode, cbody = post(base + "/buddy/travel/claim", headers, {"record_id": record_id})
        if 200 <= ccode < 300 and dig(cbody, "reward_credit") is not None:
            got = dig(cbody, "reward_credit")
            credits_gained += got
            parts.append("领旅行礼物 +%s 积分" % fmt_credit(got))
        else:
            parts.append("领旅行礼物失败（HTTP %s）" % ccode)
        travel = "idle"  # 领完后变 idle
    if travel == "idle":
        ccode, cbody = get(base + "/buddy/travel/config", headers)
        locs = dig(cbody, "locations") if (200 <= ccode < 300) else None
        if locs:
            loc = locs[0]
            dcode, dbody = post(base + "/buddy/travel/depart", headers, {"location_id": loc.get("id")})
            if 200 <= dcode < 300:
                loc_name = (dig(dbody, "location") or {}).get("name", "?")
                dur = dig(dbody, "duration_hours") or (dig(dbody, "location") or {}).get("duration_hours", "?")
                parts.append("派 Buddy 去%s（%s 小时后回）" % (loc_name, dur))
            else:
                msg = dig(dbody, "msg") or ""
                parts.append("派 Buddy 失败：%s" % (msg or ("HTTP %s" % dcode)))
    elif travel == "traveling":
        loc_name = (dig(sbody, "location") or {}).get("name", "?")
        parts.append("Buddy 旅行中（%s）" % loc_name)

    # --- 2. 盲盒/抽奖 ---
    lcode, lbody = get(base + "/lottery/chances", headers)
    chances = dig(lbody, "balance") if (200 <= lcode < 300) else 0
    if chances and chances > 0:
        dcode, dbody = post(base + "/lottery/draw", headers, {})
        if 200 <= dcode < 300:
            prize = dig(dbody, "prize_name") or dig(dbody, "prize") or "未知"
            parts.append("开盲盒获得：%s" % prize)
        else:
            parts.append("开盲盒失败（HTTP %s）" % dcode)

    # --- 3. 任务领奖 ---
    tcode, tbody = get(base + "/tasks", headers)
    if 200 <= tcode < 300:
        tasks = dig(tbody, "tasks") or []
        for t in tasks:
            done = (t.get("progress") or {}).get("current", 0) >= (t.get("progress") or {}).get("target", 1)
            if done and t.get("accept_status") != "claimed" and t.get("has_reward"):
                acode, abody = post(base + "/tasks/accept", headers, {"task_code": t.get("task_code")})
                if 200 <= acode < 300:
                    rc = t.get("reward_credit", 0)
                    re_ = t.get("reward_energy", 0)
                    credits_gained += rc
                    parts.append("领任务奖「%s」+credit%s+energy%s" % (t.get("title", t.get("task_code")), rc, re_))

    # --- 4. 能量 & 连签状态 ---
    ecode, ebody = get(base + "/energy", headers)
    energy = dig(ebody, "balance") if (200 <= ecode < 300) else None

    scode2, sbody2 = get(base + "/streak", headers)
    streak_obj = dig(sbody2, "streak") or {}
    streak_days = streak_obj.get("days") if isinstance(streak_obj, dict) else None

    # --- 5. 连签档位兑换（7d / 14d / 28d）---
    try:
        rcredits, rparts = redeem_streak_tiers(headers, endpoint, sbody2)
        credits_gained += rcredits
        parts.extend(rparts)
    except NetworkError:
        parts.append("连签兑换跳过（网络不可用）")
    except Exception as e:  # 兑换是增强项，任何异常都不应影响已完成的签到
        parts.append("连签兑换跳过（%s）" % _err_text(e))

    tail = []
    if energy is not None:
        tail.append("能量 %s" % energy)
    if streak_days is not None:
        tail.append("连签 %s 天" % streak_days)
    if credits_gained:
        tail.append("本次 +共 %s 积分" % credits_gained)

    report = "；".join(parts) if parts else "成长中心无可领取项"
    if tail:
        report += "（%s）" % "，".join(tail)
    return 0, {"result": "GROWTH", "report": report, "credits_gained": credits_gained,
               "energy": energy, "streak_days": streak_days}


def run_auto(headers, endpoint):
    """每日自动化主逻辑：查状态→未签才领→返回一行汇报。"""
    scode, sbody = post(endpoint + "/v2/billing/meter/checkin-activity-status", headers)

    if scode in (401, 403):
        return 1, {
            "result": "NO_SESSION",
            "report": "登录态已失效（HTTP %s），请重新登录 WorkBuddy 桌面端" % scode,
            "http": scode,
        }
    if not (200 <= scode < 300):
        return 1, {
            "result": "ERROR",
            "report": "签到接口返回异常（HTTP %s），可能登录态失效，请重新登录客户端" % scode,
            "http": scode,
            "status_body": sbody,
        }

    status = sbody if isinstance(sbody, dict) else {}
    active = dig(status, "active")
    activity_name = dig(status, "activity_name")

    if active is False:
        report = "签到活动未开启" + ("（%s）" % activity_name if activity_name else "")
        return 0, {"result": "INACTIVE", "report": report, "active": False}

    if dig(status, "today_checked_in") is True:
        return 0, _already_report(status)

    ccode, cbody = post(endpoint + "/v2/billing/meter/daily-checkin", headers)

    if _is_already_checked_in(cbody):
        scode2, sbody2 = post(endpoint + "/v2/billing/meter/checkin-activity-status", headers)
        fresh = sbody2 if (200 <= scode2 < 300 and isinstance(sbody2, dict)) else status
        return 0, _already_report(fresh, via="今日已签过（服务端判定已领取）")

    if ccode in (401, 403):
        return 1, {
            "result": "NO_SESSION",
            "report": "登录态已失效（HTTP %s），请重新登录 WorkBuddy 桌面端" % ccode,
            "http": ccode,
        }

    credit = dig(cbody, "credit")
    if credit is not None:
        scode2, sbody2 = post(endpoint + "/v2/billing/meter/checkin-activity-status", headers)
        fresh = sbody2 if (200 <= scode2 < 300 and isinstance(sbody2, dict)) else status
        streak_days = dig(fresh, "streak_days") or dig(status, "streak_days")
        total_credits = dig(fresh, "total_credits")
        is_streak_day = dig(fresh, "is_streak_day")
        next_streak_day = dig(fresh, "next_streak_day")
        bonus = "，且为连签奖励日" if is_streak_day else ""
        cum = "，累计 %s 积分" % fmt_credit(total_credits) if total_credits is not None else ""
        report = "成功领取 %s 积分%s（连续 %s 天%s）" % (fmt_credit(credit), bonus, streak_days, cum)
        return 0, {
            "result": "CLAIMED",
            "report": report,
            "credit": credit,
            "streak_days": streak_days,
            "total_credits": total_credits,
            "is_streak_day": is_streak_day,
            "next_streak_day": next_streak_day,
        }

    if isinstance(cbody, dict) and ("code" in cbody or "msg" in cbody):
        msg = cbody.get("msg") or ("code %s" % cbody.get("code"))
        return 1, {
            "result": "ERROR",
            "report": "领取失败：%s（HTTP %s）" % (msg, ccode),
            "http": ccode,
            "claim_body": cbody,
        }

    return 1, {
        "result": "UNKNOWN",
        "report": "未识别的领取返回，请检查接口：%s" % json.dumps(cbody, ensure_ascii=False)[:200],
        "http": ccode,
        "claim_body": cbody,
    }


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "auto"

    auth_file = find_auth_file()
    if not auth_file or not os.path.exists(auth_file):
        home = os.path.expanduser("~")
        guesses = [
            os.path.join(os.environ.get("LOCALAPPDATA", os.path.join(home, "AppData", "Local")), AUTH_BASENAME),
            os.path.join(home, "Library", "Application Support", AUTH_BASENAME),
        ]
        out = {
            "result": "NO_AUTH",
            "report": "未找到 WorkBuddy 登录凭据。请先在本机登录 WorkBuddy 桌面端；"
                      "或设置环境变量 WORKBUDDY_AUTH_FILE 指向 workbuddy-desktop.info。",
            "looked_in": guesses,
        }
        _notify("no_auth", "WorkBuddy 签到未运行",
                "未找到登录凭据，请先在本机登录 WorkBuddy 桌面端")
        print(json.dumps(out, ensure_ascii=False))
        return 2

    session = load_session(auth_file)
    try:
        headers = build_headers(session)
    except SystemExit:
        _notify("no_session", "WorkBuddy 登录态失效",
                "本地登录会话无效，请重新登录 WorkBuddy 桌面端")
        out = {"result": "NO_SESSION",
               "report": "本地登录会话无效（缺少 token/uid），请重新登录 WorkBuddy 桌面端"}
        print(json.dumps(out, ensure_ascii=False))
        return 2
    endpoint = ((session.get("auth") or {}).get("endpoint") or DEFAULT_ENDPOINT).rstrip("/")

    if action == "auto":
        try:
            code, out = run_auto(headers, endpoint)
        except NetworkError as e:
            print(json.dumps({
                "result": "NETWORK_ERROR",
                "report": "网络不可用（%s），签到未执行；将在下次定时运行时自动重试" % _err_text(e),
            }, ensure_ascii=False))
            return 3
        # 签到后顺带跑成长中心；成长中心的网络异常不应吞掉签到结果
        try:
            gcode, gout = run_growth(headers, endpoint)
        except NetworkError as e:
            gout = {"result": "NETWORK_ERROR",
                    "report": "网络不可用，跳过成长中心（%s）" % _err_text(e)}
        out["growth"] = gout.get("report")
        if gout.get("credits_gained"):
            out["report"] += "；" + gout["report"]
        if out.get("result") == "NO_SESSION" or gout.get("result") == "NO_SESSION":
            _notify("no_session", "WorkBuddy 登录态失效",
                    "签到失败：登录态已失效，请重新登录 WorkBuddy 桌面端")
        print(json.dumps(out, ensure_ascii=False))
        return code

    if action == "growth":
        try:
            code, out = run_growth(headers, endpoint)
        except NetworkError as e:
            print(json.dumps({
                "result": "NETWORK_ERROR",
                "report": "网络不可用（%s），成长中心未执行；将在下次定时运行时自动重试" % _err_text(e),
            }, ensure_ascii=False))
            return 3
        if out.get("result") == "NO_SESSION":
            _notify("no_session", "WorkBuddy 登录态失效",
                    "成长中心失败：登录态已失效，请重新登录 WorkBuddy 桌面端")
        print(json.dumps(out, ensure_ascii=False))
        return code

    if action in ("status", "all"):
        try:
            scode, sbody = post(endpoint + "/v2/billing/meter/checkin-activity-status", headers)
        except NetworkError as e:
            print(json.dumps({"step": "status", "result": "NETWORK_ERROR",
                              "report": "网络不可用（%s）" % _err_text(e)},
                             ensure_ascii=False))
            return 3
        print(json.dumps({"step": "status", "http": scode, "body": sbody}, ensure_ascii=False))

    if action in ("claim", "all"):
        try:
            ccode, cbody = post(endpoint + "/v2/billing/meter/daily-checkin", headers)
        except NetworkError as e:
            print(json.dumps({"step": "claim", "result": "NETWORK_ERROR",
                              "report": "网络不可用（%s）" % _err_text(e)},
                             ensure_ascii=False))
            return 3
        print(json.dumps({"step": "claim", "http": ccode, "body": cbody}, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except NetworkError as e:
        # 兜底：任何逃逸到顶层的网络异常都输出干净 JSON，不往日志里吐 traceback
        print(json.dumps({
            "result": "NETWORK_ERROR",
            "report": "网络不可用（%s），本次未执行；将在下次定时运行时自动重试" % _err_text(e),
        }, ensure_ascii=False))
        sys.exit(3)
