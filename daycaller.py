"""
DayCaller - "calls" you and reminds you according to how you schedule your day.

When a reminder is due it:
  * rings your PC like an incoming call (popup with Answer / Snooze / Decline),
  * reads the reminder out loud when you answer,
  * optionally places a REAL phone call to your mobile via Twilio (see README).

Standard library only (Python 3.9+, Windows).

Usage:
  python daycaller.py plan                         # type out today's schedule line by line
  python daycaller.py add 07:30 "Wake up and stretch" --days daily
  python daycaller.py add 14:00 "Team meeting" --days weekdays
  python daycaller.py add 18:45 "Pick up the kids" --date 2026-11-12
  python daycaller.py list
  python daycaller.py remove 3
  python daycaller.py clear-today                  # drop today's one-off items
  python daycaller.py test "This is a test call"   # ring right now
  python daycaller.py run                          # start the caller (keep it running)
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEDULE_FILE = os.path.join(HERE, "schedule.json")
CONFIG_FILE = os.path.join(HERE, "config.json")
LOG_FILE = os.path.join(HERE, "daycaller.log")

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_GROUPS = {
    "daily": DAY_NAMES,
    "weekdays": DAY_NAMES[:5],
    "weekends": DAY_NAMES[5:],
}

STATE_FILE = os.path.join(HERE, "twilio_state.json")   # remembers the audio-hosting service
AUDIO_DIR = os.path.join(HERE, "audio")

DEFAULT_CONFIG = {
    # "local" = ring this PC, "phone" = real call via Twilio, "both" = both
    "mode": "local",
    "your_name": "",
    # "en" = English, "sw" = Swahili
    "language": "en",
    # Voice used on the PC (and for Swahili phone calls). English male: en-US-GuyNeural,
    # en-GB-RyanNeural. Swahili male: sw-TZ-DaudiNeural.
    "voice": "en-US-GuyNeural",
    # Twilio voice for English phone calls (male): Polly.Matthew-Neural, Polly.Brian-Neural
    "phone_voice": "Polly.Matthew-Neural",
    "snooze_minutes": 10,
    "ring_seconds": 60,          # how long the PC rings before counting as missed
    "missed_retry_minutes": 5,   # re-ring after a missed call
    "missed_max_retries": 2,
    "twilio": {
        "account_sid": "",
        "auth_token": "",
        "from_number": "",       # your Twilio number, e.g. +15551234567
        "to_number": "",         # your mobile, e.g. +2348012345678
    },
}


# --------------------------------------------------------------------------- storage
def log(msg: str) -> None:
    line = f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_json(path: str, default):
    if not os.path.exists(path):
        return json.loads(json.dumps(default))
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def load_schedule() -> dict:
    data = load_json(SCHEDULE_FILE, {"next_id": 1, "reminders": []})
    data.setdefault("next_id", 1)
    data.setdefault("reminders", [])
    return data


def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    user = load_json(CONFIG_FILE, {})
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    # environment variables override the file (keeps secrets out of it if you prefer)
    env_map = {
        "TWILIO_ACCOUNT_SID": "account_sid",
        "TWILIO_AUTH_TOKEN": "auth_token",
        "TWILIO_FROM": "from_number",
        "MY_PHONE": "to_number",
    }
    for env, key in env_map.items():
        if os.environ.get(env):
            cfg["twilio"][key] = os.environ[env]
    return cfg


# --------------------------------------------------------------------------- parsing
def parse_time(text: str) -> str:
    text = text.strip().lower().replace(".", ":")
    for fmt in ("%H:%M", "%I:%M%p", "%I:%M %p", "%I%p", "%I %p", "%H%M"):
        try:
            return dt.datetime.strptime(text, fmt).strftime("%H:%M")
        except ValueError:
            continue
    raise ValueError(f"Can't understand time '{text}'. Use e.g. 07:30, 7:30pm, 9am.")


def parse_days(text: str) -> list[str]:
    text = text.strip().lower()
    if text in DAY_GROUPS:
        return list(DAY_GROUPS[text])
    days = [d.strip()[:3] for d in text.split(",") if d.strip()]
    bad = [d for d in days if d not in DAY_NAMES]
    if bad:
        raise ValueError(f"Unknown day(s): {', '.join(bad)}. Use mon,tue,... or daily/weekdays/weekends.")
    return days


def describe_when(r: dict) -> str:
    if r.get("date"):
        return r["date"]
    days = r.get("days", [])
    for name, group in DAY_GROUPS.items():
        if days == group:
            return name
    return ",".join(days)


def is_due_on(r: dict, day: dt.date) -> bool:
    if r.get("date"):
        return r["date"] == day.isoformat()
    return DAY_NAMES[day.weekday()] in r.get("days", [])


# --------------------------------------------------------------------------- language
TEXTS = {
    "en": {
        "greeting": "Hi {name}. This is your reminder. {message}.",
        "again": "Again: {message}. Goodbye.",
        "incoming": "📞  Incoming reminder",
        "answer": "Answer", "snooze": "Snooze {m}m", "decline": "Decline",
    },
    "sw": {
        "greeting": "Habari {name}. Huu ni ukumbusho wako. {message}.",
        "again": "Narudia: {message}. Kwaheri.",
        "incoming": "📞  Ukumbusho unaingia",
        "answer": "Pokea", "snooze": "Ahirisha {m}d", "decline": "Kataa",
    },
}


def tr(cfg: dict, key: str, **kw) -> str:
    texts = TEXTS.get(cfg.get("language", "en"), TEXTS["en"])
    out = texts[key].format(**kw)
    return " ".join(out.split()).replace(" .", ".")


def spoken_script(message: str, cfg: dict) -> str:
    name = cfg.get("your_name") or ""
    return tr(cfg, "greeting", name=name, message=message) + " " + tr(cfg, "again", message=message)


def make_audio(text: str, cfg: dict) -> str:
    """Create an MP3 of `text` with a natural neural voice (needs internet + edge-tts)."""
    import asyncio
    import hashlib
    import edge_tts  # pip install edge-tts

    os.makedirs(AUDIO_DIR, exist_ok=True)
    voice = cfg.get("voice", "sw-TZ-RehemaNeural")
    digest = hashlib.sha256(f"{voice}|{text}".encode()).hexdigest()[:20]
    path = os.path.join(AUDIO_DIR, f"{digest}.mp3")
    if not os.path.exists(path):
        asyncio.run(edge_tts.Communicate(text, voice, rate="-5%").save(path))
    return path


def play_mp3(path: str) -> None:
    """Play an MP3 on this PC and wait until it finishes (Windows MCI, no extra installs)."""
    import ctypes
    mci = ctypes.windll.winmm.mciSendStringW
    alias = "daycaller_audio"
    mci(f"close {alias}", None, 0, None)
    if mci(f'open "{path}" type mpegvideo alias {alias}', None, 0, None) != 0:
        raise RuntimeError("could not open audio")
    mci(f"play {alias} wait", None, 0, None)
    mci(f"close {alias}", None, 0, None)


# --------------------------------------------------------------------------- Twilio audio hosting
def _twilio_request(cfg: dict, method: str, url: str, fields: dict | None = None,
                    body: bytes | None = None, content_type: str | None = None) -> dict:
    t = cfg["twilio"]
    if fields is not None:
        body = urllib.parse.urlencode(fields, doseq=True).encode()
        content_type = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, method=method)
    token = base64.b64encode(f"{t['account_sid']}:{t['auth_token']}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Twilio HTTP {e.code}: {e.read().decode(errors='ignore')[:300]}") from None


def host_audio(path: str, cfg: dict) -> str:
    """Upload the MP3 as a public asset in a Twilio Serverless service and return its URL,
    so Twilio can <Play> it during the call. The service is created once and reused."""
    import uuid
    api = "https://serverless.twilio.com/v1"
    state = load_json(STATE_FILE, {})
    if state.get("account_sid") != cfg["twilio"]["account_sid"]:
        state = {"account_sid": cfg["twilio"]["account_sid"]}

    if not state.get("service_sid"):
        svc = _twilio_request(cfg, "POST", f"{api}/Services", {
            "UniqueName": f"daycaller-{uuid.uuid4().hex[:8]}",
            "FriendlyName": "DayCaller audio",
        })
        state["service_sid"] = svc["sid"]
        save_json(STATE_FILE, state)
    s = state["service_sid"]

    if not state.get("environment_sid"):
        env = _twilio_request(cfg, "POST", f"{api}/Services/{s}/Environments",
                              {"UniqueName": "production"})
        state["environment_sid"], state["domain"] = env["sid"], env["domain_name"]
        save_json(STATE_FILE, state)

    if not state.get("asset_sid"):
        asset = _twilio_request(cfg, "POST", f"{api}/Services/{s}/Assets",
                                {"FriendlyName": "reminder"})
        state["asset_sid"] = asset["sid"]
        save_json(STATE_FILE, state)

    # random file name so the URL can't be guessed
    public_path = f"/r-{uuid.uuid4().hex}.mp3"
    boundary = uuid.uuid4().hex
    with open(path, "rb") as f:
        data = f.read()
    parts = []
    for k, v in (("Path", public_path), ("Visibility", "public")):
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="Content"; '
                 f'filename="reminder.mp3"\r\nContent-Type: audio/mpeg\r\n\r\n'.encode() + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    version = _twilio_request(
        cfg, "POST",
        f"https://serverless-upload.twilio.com/v1/Services/{s}/Assets/{state['asset_sid']}/Versions",
        body=b"".join(parts), content_type=f"multipart/form-data; boundary={boundary}")

    build = _twilio_request(cfg, "POST", f"{api}/Services/{s}/Builds",
                            {"AssetVersions": [version["sid"]]})
    for _ in range(60):  # wait up to ~2 minutes for the build
        status = _twilio_request(cfg, "GET", f"{api}/Services/{s}/Builds/{build['sid']}/Status")["status"]
        if status == "completed":
            break
        if status == "failed":
            raise RuntimeError("Twilio build failed")
        time.sleep(2)
    else:
        raise RuntimeError("Twilio build timed out")

    _twilio_request(cfg, "POST", f"{api}/Services/{s}/Environments/{state['environment_sid']}/Deployments",
                    {"BuildSid": build["sid"]})
    return f"https://{state['domain']}{public_path}"


# --------------------------------------------------------------------------- the "call"
def speak_message(message: str, cfg: dict) -> None:
    """Read the reminder aloud on this PC in the configured language."""
    script = spoken_script(message, cfg)
    if cfg.get("voice"):
        try:
            play_mp3(make_audio(script, cfg))
            return
        except Exception as e:  # noqa: BLE001
            log(f"Neural voice failed on PC ({e}); using Windows voice instead")
    speak(script)


def speak(text: str) -> None:
    """Read text aloud with the built-in Windows voice."""
    safe = text.replace("'", "''")
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.Rate = 0; "
        f"$s.Speak('{safe}')"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as e:  # noqa: BLE001
        log(f"Speech failed: {e}")


def ring_loop(stop: threading.Event) -> None:
    """Phone-like ring pattern until stopped."""
    try:
        import winsound
    except ImportError:
        return
    while not stop.is_set():
        for _ in range(2):
            if stop.is_set():
                return
            winsound.Beep(880, 350)
            winsound.Beep(660, 350)
        stop.wait(1.5)


def ring_pc(message: str, cfg: dict) -> str:
    """Show an incoming-call popup. Returns 'answered', 'snoozed', 'declined' or 'missed'."""
    import tkinter as tk

    result = {"value": "missed"}
    stop = threading.Event()
    threading.Thread(target=ring_loop, args=(stop,), daemon=True).start()

    root = tk.Tk()
    root.title("DayCaller - Incoming call")
    root.attributes("-topmost", True)
    root.configure(bg="#111827")
    root.resizable(False, False)
    w, h = 380, 230
    x = root.winfo_screenwidth() - w - 30
    y = root.winfo_screenheight() - h - 80
    root.geometry(f"{w}x{h}+{x}+{y}")

    tk.Label(root, text=tr(cfg, "incoming"), fg="#9ca3af", bg="#111827",
             font=("Segoe UI", 10)).pack(pady=(18, 4))
    tk.Label(root, text=message, fg="white", bg="#111827", wraplength=340,
             font=("Segoe UI", 15, "bold"), justify="center").pack(pady=(0, 6))
    tk.Label(root, text=dt.datetime.now().strftime("%I:%M %p").lstrip("0"),
             fg="#9ca3af", bg="#111827", font=("Segoe UI", 10)).pack()

    def finish(value: str) -> None:
        result["value"] = value
        stop.set()
        root.destroy()

    btns = tk.Frame(root, bg="#111827")
    btns.pack(pady=16)
    style = dict(fg="white", font=("Segoe UI", 10, "bold"), relief="flat",
                 width=10, pady=6, cursor="hand2", bd=0)
    tk.Button(btns, text=tr(cfg, "answer"), bg="#16a34a", activebackground="#15803d",
              command=lambda: finish("answered"), **style).pack(side="left", padx=5)
    tk.Button(btns, text=tr(cfg, "snooze", m=cfg["snooze_minutes"]), bg="#2563eb",
              activebackground="#1d4ed8", command=lambda: finish("snoozed"),
              **style).pack(side="left", padx=5)
    tk.Button(btns, text=tr(cfg, "decline"), bg="#dc2626", activebackground="#b91c1c",
              command=lambda: finish("declined"), **style).pack(side="left", padx=5)

    root.protocol("WM_DELETE_WINDOW", lambda: finish("declined"))
    root.after(int(cfg["ring_seconds"]) * 1000, lambda: finish("missed"))
    root.lift()
    root.focus_force()
    root.mainloop()
    stop.set()

    if result["value"] == "answered":
        speak_message(message, cfg)
    return result["value"]


def phone_call(message: str, cfg: dict) -> bool:
    """Place a real phone call using Twilio's REST API. Returns True on success."""
    t = cfg["twilio"]
    missing = [k for k in ("account_sid", "auth_token", "from_number", "to_number") if not t.get(k)]
    if missing:
        log(f"Phone call skipped - Twilio settings missing: {', '.join(missing)}")
        return False
    twiml = None
    if cfg.get("language", "en") != "en":
        try:
            audio_url = host_audio(make_audio(spoken_script(message, cfg), cfg), cfg)
            twiml = f'<Response><Pause length="1"/><Play>{escape(audio_url)}</Play></Response>'
        except Exception as e:  # noqa: BLE001
            log(f"Swahili audio failed ({e}); falling back to Twilio's built-in voice")
    if twiml is None:
        name = cfg.get("your_name") or ""
        spoken = escape(tr(cfg, "greeting", name=name, message=message))
        v = escape(cfg.get("phone_voice") or "Polly.Matthew-Neural", {'"': "&quot;"})
        twiml = (
            "<Response>"
            f'<Pause length="1"/><Say voice="{v}">{spoken}</Say><Pause length="1"/>'
            f'<Say voice="{v}">{escape(tr(cfg, "again", message=message))}</Say>'
            "</Response>"
        )
    url = f"https://api.twilio.com/2010-04-01/Accounts/{t['account_sid']}/Calls.json"
    body = urllib.parse.urlencode({"To": t["to_number"], "From": t["from_number"], "Twiml": twiml}).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    token = base64.b64encode(f"{t['account_sid']}:{t['auth_token']}".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            sid = json.loads(resp.read().decode()).get("sid")
            log(f"Phone call placed to {t['to_number']} (call sid {sid})")
            return True
    except urllib.error.HTTPError as e:
        log(f"Phone call failed: HTTP {e.code} {e.read().decode(errors='ignore')[:300]}")
    except Exception as e:  # noqa: BLE001
        log(f"Phone call failed: {e}")
    return False


def deliver(message: str, cfg: dict) -> str:
    mode = cfg.get("mode", "local")
    outcome = "answered"
    if mode in ("phone", "both"):
        ok = phone_call(message, cfg)
        if mode == "phone" and not ok:
            mode = "local"  # fall back so you still get reminded
    if mode in ("local", "both"):
        outcome = ring_pc(message, cfg)
    return outcome


# --------------------------------------------------------------------------- runner
def run() -> None:
    cfg = load_config()
    log(f"DayCaller running (mode: {cfg['mode']}). Press Ctrl+C to stop.")
    fired: set[str] = set()
    extra: list[dict] = []  # snoozes / retries: {"at": datetime, "message": str, "tries": int}
    started = dt.datetime.now().replace(second=0, microsecond=0)

    while True:
        now = dt.datetime.now()
        cfg = load_config()              # pick up edits without restarting
        schedule = load_schedule()
        today = now.date()
        hhmm = now.strftime("%H:%M")

        due: list[tuple[str, int]] = []
        for r in schedule["reminders"]:
            if not is_due_on(r, today):
                continue
            key = f"{r['id']}|{today}|{r['time']}"
            r_time = dt.datetime.combine(today, dt.datetime.strptime(r["time"], "%H:%M").time())
            # fire within a 2-minute window (covers sleep/lag) but never for times before start
            if key not in fired and r_time >= started and r_time <= now < r_time + dt.timedelta(minutes=2):
                fired.add(key)
                due.append((r["message"], 0))

        for item in list(extra):
            if now >= item["at"]:
                extra.remove(item)
                due.append((item["message"], item["tries"]))

        for message, tries in due:
            log(f"Calling: {message}")
            outcome = deliver(message, cfg)
            log(f"  -> {outcome}")
            if outcome == "snoozed":
                extra.append({"at": now + dt.timedelta(minutes=int(cfg["snooze_minutes"])),
                              "message": message, "tries": tries})
            elif outcome == "missed" and tries < int(cfg["missed_max_retries"]):
                extra.append({"at": now + dt.timedelta(minutes=int(cfg["missed_retry_minutes"])),
                              "message": message, "tries": tries + 1})
            now = dt.datetime.now()

        # tidy up expired one-off reminders once a day-ish
        if hhmm == "00:05":
            prune_old(schedule)
        time.sleep(15)


def prune_old(schedule: dict) -> None:
    today = dt.date.today().isoformat()
    before = len(schedule["reminders"])
    schedule["reminders"] = [r for r in schedule["reminders"] if not r.get("date") or r["date"] >= today]
    if len(schedule["reminders"]) != before:
        save_json(SCHEDULE_FILE, schedule)


# --------------------------------------------------------------------------- commands
def add_reminder(time_str: str, message: str, days: str | None, date: str | None) -> dict:
    schedule = load_schedule()
    r = {"id": schedule["next_id"], "time": parse_time(time_str), "message": message.strip()}
    if date:
        r["date"] = dt.date.fromisoformat(date).isoformat()
    elif days:
        r["days"] = parse_days(days)
    else:
        r["date"] = dt.date.today().isoformat()   # default: just today
    schedule["next_id"] += 1
    schedule["reminders"].append(r)
    save_json(SCHEDULE_FILE, schedule)
    return r


def cmd_list(_args) -> None:
    schedule = load_schedule()
    rs = sorted(schedule["reminders"], key=lambda r: (r.get("date", ""), r["time"]))
    if not rs:
        print("No reminders yet. Try:  python daycaller.py plan")
        return
    today = dt.date.today()
    print(f"{'ID':>3}  {'TIME':5}  {'WHEN':12}  {'TODAY':5}  MESSAGE")
    for r in sorted(rs, key=lambda r: r["time"]):
        mark = "yes" if is_due_on(r, today) else ""
        print(f"{r['id']:>3}  {r['time']:5}  {describe_when(r):12}  {mark:5}  {r['message']}")


def cmd_add(args) -> None:
    r = add_reminder(args.time, args.message, args.days, args.date)
    print(f"Added #{r['id']}: {r['time']} ({describe_when(r)}) - {r['message']}")


def cmd_remove(args) -> None:
    schedule = load_schedule()
    before = len(schedule["reminders"])
    schedule["reminders"] = [r for r in schedule["reminders"] if r["id"] not in args.ids]
    save_json(SCHEDULE_FILE, schedule)
    print(f"Removed {before - len(schedule['reminders'])} reminder(s).")


def cmd_clear_today(_args) -> None:
    schedule = load_schedule()
    today = dt.date.today().isoformat()
    before = len(schedule["reminders"])
    schedule["reminders"] = [r for r in schedule["reminders"] if r.get("date") != today]
    save_json(SCHEDULE_FILE, schedule)
    print(f"Cleared {before - len(schedule['reminders'])} one-off reminder(s) for today.")


def cmd_plan(args) -> None:
    day = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    print(f"Plan for {day:%A %d %B}. One item per line:  TIME  what to do")
    print("  e.g.  7:30am Morning workout")
    print("        13:00  Lunch with Sam")
    print("Press Enter on an empty line when done.\n")
    count = 0
    while True:
        try:
            line = input("> ").replace("﻿", "").strip()
        except EOFError:
            break
        if not line:
            break
        parts = line.split(None, 1)
        # allow "7:30 pm Something"
        if len(parts) == 2 and parts[1].lower().startswith(("am ", "pm ")):
            parts = [parts[0] + parts[1][:2], parts[1][3:]]
        if len(parts) < 2:
            print("  ! need a time and a message")
            continue
        try:
            r = add_reminder(parts[0], parts[1], None, day.isoformat())
            print(f"  ok  {r['time']}  {r['message']}")
            count += 1
        except ValueError as e:
            print(f"  ! {e}")
    print(f"\nAdded {count} reminder(s). Start the caller with:  python daycaller.py run")


def cmd_test(args) -> None:
    cfg = load_config()
    print("Ringing now...")
    print("Outcome:", deliver(args.message, cfg))


def cmd_cloud(args) -> None:
    """Used by the GitHub Actions workflow: phone-call any reminder due in the next
    `--window` minutes (waiting until its exact time), so calls work with the PC off."""
    cfg = load_config()
    if args.message:  # manual test from GitHub
        sys.exit(0 if phone_call(args.message, cfg) else 1)
    now = dt.datetime.now()
    today = now.date()
    due = []
    for r in load_schedule()["reminders"]:
        if not is_due_on(r, today):
            continue
        at = dt.datetime.combine(today, dt.datetime.strptime(r["time"], "%H:%M").time())
        # GitHub can start scheduled jobs late, so also accept reminders up to 30 min past
        if now - dt.timedelta(minutes=30) <= at <= now + dt.timedelta(minutes=args.window):
            due.append((at, r["message"]))
    if not due:
        log(f"No reminders due between now and +{args.window} min ({now:%A %H:%M}).")
        return
    ok = True
    for at, message in sorted(due):
        wait = (at - dt.datetime.now()).total_seconds()
        if wait > 0:
            log(f"Waiting {int(wait // 60)} min until {at:%H:%M} for: {message}")
            time.sleep(wait)
        ok = phone_call(message, cfg) and ok
    sys.exit(0 if ok else 1)


def cmd_setup(_args) -> None:
    cfg = load_json(CONFIG_FILE, DEFAULT_CONFIG)
    print("DayCaller setup (press Enter to keep the current value)\n")
    name = input(f"Your name [{cfg.get('your_name', '')}]: ").strip()
    if name:
        cfg["your_name"] = name
    mode = input(f"Mode - local / phone / both [{cfg.get('mode', 'local')}]: ").strip().lower()
    if mode in ("local", "phone", "both"):
        cfg["mode"] = mode
    if cfg["mode"] in ("phone", "both"):
        tw = cfg.setdefault("twilio", dict(DEFAULT_CONFIG["twilio"]))
        print("\nTwilio details (from https://console.twilio.com):")
        for key, label in [("account_sid", "Account SID"), ("auth_token", "Auth token"),
                           ("from_number", "Twilio phone number (+countrycode...)"),
                           ("to_number", "YOUR mobile number (+countrycode...)")]:
            shown = "****" if key == "auth_token" and tw.get(key) else tw.get(key, "")
            val = input(f"  {label} [{shown}]: ").strip()
            if val:
                tw[key] = val
    save_json(CONFIG_FILE, cfg)
    print(f"\nSaved to {CONFIG_FILE}")


def main() -> None:
    p = argparse.ArgumentParser(description="DayCaller - calls you with reminders from your daily schedule.")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="add a reminder")
    a.add_argument("time", help="e.g. 07:30, 7:30pm, 9am")
    a.add_argument("message")
    g = a.add_mutually_exclusive_group()
    g.add_argument("--days", help="daily | weekdays | weekends | mon,wed,fri")
    g.add_argument("--date", help="YYYY-MM-DD (one-off). Default: today only")
    a.set_defaults(func=cmd_add)

    sub.add_parser("list", help="show reminders").set_defaults(func=cmd_list)

    r = sub.add_parser("remove", help="remove reminder(s) by id")
    r.add_argument("ids", type=int, nargs="+")
    r.set_defaults(func=cmd_remove)

    sub.add_parser("clear-today", help="remove today's one-off reminders").set_defaults(func=cmd_clear_today)

    pl = sub.add_parser("plan", help="type out your day's schedule")
    pl.add_argument("--date", help="plan another day, YYYY-MM-DD")
    pl.set_defaults(func=cmd_plan)

    t = sub.add_parser("test", help="ring right now")
    t.add_argument("message", nargs="?", default="This is a test call from DayCaller.")
    t.set_defaults(func=cmd_test)

    sub.add_parser("setup", help="set your name and phone-call settings").set_defaults(func=cmd_setup)
    sub.add_parser("run", help="start the caller").set_defaults(func=lambda _a: run())

    cl = sub.add_parser("cloud", help="(GitHub Actions) phone-call reminders due soon")
    cl.add_argument("--window", type=int, default=90, help="minutes ahead to look")
    cl.add_argument("--message", help="call right now with this message (test)")
    cl.set_defaults(func=cmd_cloud)

    args = p.parse_args()
    try:
        args.func(args)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
