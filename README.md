# 📞 DayCaller

**Your schedule calls you.** DayCaller rings your phone (a real call) and your PC before the things in your day, like your first lecture, a meeting or the gym, and reads the reminder to you out loud.

I built it because alarms are easy to ignore and a phone call isn't. It runs in GitHub Actions, so **your phone still gets called when your computer is off**.

```
06:30  📱 Ring ring...
       "Hi. This is your reminder. Your first class today is Data Structures
        at 8:30 AM in Room 101. Get ready."
```

## Features

- 📱 **Real phone calls** through Twilio, to any country Twilio supports.
- ☁️ **Works with your PC off.** A GitHub Actions cron job places the calls.
- 💻 **PC "incoming call" popup** with Answer / Snooze / Decline. It rings until you respond and calls back if you miss it.
- 🗣️ **Natural voices**, male or female. Swahili is supported too 🇹🇿 with neural voices (`sw-TZ-DaudiNeural`, `sw-TZ-RehemaNeural`), even though Twilio itself has no Swahili voice.
- 🗓️ **Flexible schedule:** daily, weekdays, weekends, specific days, or one-off dates.
- ✍️ **Plan your day in seconds:** type lines like `7:30am Gym` or `13:00 Lunch with Sam`.
- 🪶 **Pure Python standard library.** `edge-tts` is optional, only for neural voices.

## Quick start (PC only, free)

```bash
git clone https://github.com/ezekiel3x/daycaller.git
cd daycaller
python daycaller.py plan       # type your day: "7:30am Morning workout"
python daycaller.py run        # keep it running; your PC rings at each time
```

More commands:

```bash
python daycaller.py add 07:00 "Wake up" --days daily
python daycaller.py add 14:00 "Team meeting" --days mon,wed
python daycaller.py add 18:45 "Pick up the kids" --date 2026-12-01
python daycaller.py list
python daycaller.py remove 3
python daycaller.py test "Is this thing on?"
```

On Windows, double-click **Start DayCaller.bat**, or put a shortcut to it in `shell:startup` so it starts when you log in.

## Real phone calls

1. Create a free [Twilio](https://www.twilio.com/try-twilio) account, get a phone number, and on a trial account verify your mobile number.
2. Run `python daycaller.py setup`, choose `phone` or `both`, and enter your Account SID, Auth Token, Twilio number and mobile number. These are saved to `config.json`, which is git-ignored.
3. Run `python daycaller.py test`. Your phone rings.

> Calling outside the US? Enable your country under Twilio Console → Voice → Settings → **Geo Permissions**.

## Calls with your PC off (GitHub Actions)

1. Fork this repo. You can make your copy **private** to keep your schedule to yourself.
2. Edit `schedule.json` with your reminders.
3. Add the repository secrets (Settings → Secrets and variables → Actions):
   `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM`, `MY_PHONE`.
4. In `.github/workflows/reminder-calls.yml`, uncomment `schedule:`, set your cron times (in UTC), and set `TZ` to your time zone.
5. Go to Actions → **Reminder calls** → **Run workflow** to get a test call right away.

Each run starts about 15 minutes early and waits for the exact time, because GitHub sometimes starts scheduled jobs late.

## Settings (`config.json`)

| Key | Default | Meaning |
|---|---|---|
| `mode` | `local` | `local` (PC), `phone` (Twilio), `both` |
| `language` | `en` | `en` or `sw` (Swahili) |
| `voice` | `en-US-GuyNeural` | Neural voice for the PC and Swahili calls |
| `phone_voice` | `Polly.Matthew-Neural` | Twilio voice for English calls |
| `your_name` | | Used in the greeting ("Hi Alex…") |
| `snooze_minutes` | `10` | Snooze length |
| `missed_retry_minutes` | `5` | Call back after a missed call |

## How it works

```
schedule.json ──► daycaller.py ──► PC popup + voice (local)
                       │
                       └──► Twilio REST API ──► 📱 your phone
GitHub Actions cron ──► daycaller.py cloud ──┘   (PC can be off)
```

For Swahili, the message is synthesized with a neural voice, uploaded as an asset to your own Twilio Serverless service, and played during the call with `<Play>`.

## License

MIT. If this helps you wake up for class, consider leaving a ⭐
