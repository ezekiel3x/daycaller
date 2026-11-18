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
- ☁️ **Works with your PC off.** GitHub Actions places the calls, triggered on time by a free external scheduler.
- ✅ **Press any key to confirm.** If you don't, DayCaller calls back up to 2 more times, 5 minutes apart. A call that a carrier or voicemail picks up doesn't count as heard.
- 🛡️ **No double calls**, even if two triggers fire for the same reminder.
- 💻 **PC "incoming call" popup** with Answer / Snooze / Decline. It rings until you respond and calls back if you miss it.
- 🗣️ **Natural voices**, male or female. Swahili is supported too 🇹🇿 with neural voices (`sw-TZ-DaudiNeural`, `sw-TZ-RehemaNeural`), even though Twilio itself has no Swahili voice. Swahili voices work when calls are placed from your PC (`pip install edge-tts`); the GitHub Actions setup is English-first.
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
4. In `.github/workflows/reminder-calls.yml`, set `TZ` to your time zone.
5. Go to Actions → **Reminder calls** → **Run workflow** to get a test call right away. Press any key when it asks.
6. Set up the on-time trigger below.

### On-time trigger (cron-job.org)

GitHub's built-in `schedule:` can start hours late, so a free external scheduler starts the workflow instead.

1. Create a [fine-grained GitHub token](https://github.com/settings/personal-access-tokens/new) with access to only your DayCaller repo and the permission **Contents: Read and write**.
2. At [cron-job.org](https://console.cron-job.org/signup), create one job for each distinct reminder time, set to run **5 minutes before** it:

   | Setting | Value |
   |---|---|
   | URL | `https://api.github.com/repos/YOUR-USERNAME/YOUR-REPO/dispatches` |
   | Schedule | Your days, 5 minutes before the reminder |
   | Time zone | Your time zone |
   | Request method | `POST` |
   | HTTP authentication | Username: your GitHub username. Password: your token |
   | Header | `Accept: application/vnd.github+json` |
   | Request body | `{"event_type":"reminder"}` |

3. Use **Test run** on the job. `204 No Content` means it works. No call is placed unless a reminder is due.

The job only wakes the workflow. The workflow reads `schedule.json` to decide what to say, so one job can cover several days that share a time.

### Press any key to confirm

Twilio reports a call as `completed` whenever anything answers, including a carrier announcement or voicemail. So each call asks you to press a key. The first cloud call deploys a small `/confirm` function to your own Twilio Serverless service, and DayCaller uses it to tell whether you really heard the reminder.

> Each callback is a separate billed call. Check Twilio's rates for your country.

## Settings (`config.json`)

| Key | Default | Meaning |
|---|---|---|
| `mode` | `local` | `local` (PC), `phone` (Twilio), `both` |
| `language` | `en` | `en` or `sw` (Swahili) |
| `voice` | `en-US-GuyNeural` | Neural voice for the PC and Swahili calls |
| `phone_voice` | `Polly.Matthew-Neural` | Twilio voice for English calls |
| `your_name` | | Used in the greeting ("Hi Sam…") |
| `snooze_minutes` | `10` | Snooze length |
| `missed_retry_minutes` | `5` | Minutes before calling back |
| `missed_max_retries` | `2` | Extra calls if you don't confirm |

## How it works

```
schedule.json ──► daycaller.py ──► PC popup + voice (local)
                       │
                       └──► Twilio REST API ──► 📱 your phone
cron-job.org ──► GitHub Actions ──► daycaller.py cloud ──┘   (PC can be off)
                                         ▲
                     no key pressed? ────┘ call back in 5 min (up to 3 calls)
```

For Swahili, the message is synthesized with a neural voice, uploaded as an asset to your own Twilio Serverless service, and played during the call with `<Play>`.

## License

MIT. If this helps you wake up for class, consider leaving a ⭐
