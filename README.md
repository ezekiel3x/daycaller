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

## Choose your setup

| Setup | What you get | PC must stay on? | Cost | You need |
|---|---|---|---|---|
| **[A. PC only](#a-pc-only)** | Popup and voice on your computer | Yes | Free | Windows, Python |
| **[B. PC + phone](#b-pc--phone-calls)** | Setup A plus real phone calls | Yes | Twilio call rates | Setup A, Twilio account |
| **[C. Cloud](#c-cloud-calls-with-your-pc-off)** (recommended for phone calls) | Real phone calls | **No** | Twilio call rates | Twilio, GitHub and cron-job.org accounts |

## Install

### Requirements

- **Python 3.9 or newer**
- **Git**
- **Windows 10 or 11** for the PC popup and voice. Setup C runs in the cloud, so you can manage it from any operating system.

On Windows, install both from a terminal:

```bash
winget install Python.Python.3.12
winget install Git.Git
```

Close the terminal, open a new one, and check that both work:

```bash
python --version
git --version
```

If you install Python from [python.org](https://www.python.org/downloads/) instead, tick **Add python.exe to PATH** in the installer.

### Download DayCaller

```bash
git clone https://github.com/ezekiel3x/daycaller.git
cd daycaller
```

Optional: install natural voices for the PC. Without them, DayCaller uses the built-in Windows voice.

```bash
python -m pip install -r requirements.txt
```

## A. PC only

`schedule.json` comes with example reminders. See them, then remove them:

```bash
python daycaller.py list
python daycaller.py remove 1 2 3
```

Add your day and start the caller:

```bash
python daycaller.py plan       # type your day: "7:30am Morning workout"
python daycaller.py test       # ring the PC now
python daycaller.py run        # keep it running; your PC rings at each time
```

The window must stay open and the PC must stay awake.

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

## Twilio account

Setups B and C both need this.

1. Create an account at [Twilio](https://www.twilio.com/try-twilio).
2. In the [Twilio Console](https://console.twilio.com), get a phone number.
3. Copy your **Account SID** and **Auth Token** from the Console home page.
4. On a trial account, add your mobile under **Phone Numbers → Manage → Verified Caller IDs**. Trial accounts can only call verified numbers.
5. Calling outside the US? Enable your country under **Voice → Settings → Geo Permissions**.

Write phone numbers in international format, with no spaces: `+15551234567`.

**Trial accounts:** each call starts with a short Twilio notice, and you may have to press a key to hear your reminder. Upgrading removes the notice. Calls are billed per minute, and rates depend on the country, so check [Twilio's voice pricing](https://www.twilio.com/en-us/voice/pricing).

## B. PC + phone calls

1. Finish [Setup A](#a-pc-only) and create your [Twilio account](#twilio-account).
2. Run `python daycaller.py setup`, choose `phone` or `both`, and enter your Account SID, Auth Token, Twilio number and mobile number. These are saved to `config.json`, which is git-ignored.
3. Run `python daycaller.py test`. Your phone rings.

## C. Cloud calls with your PC off

### 1. Make your own private copy

Your schedule shows where you will be and when, so keep it private. **Don't use GitHub's Fork button**, because a fork of a public repo can't be made private.

Create an empty **private** repository at [github.com/new](https://github.com/new), without a README. Then run these commands, using your own username and repository name:

```bash
git clone https://github.com/ezekiel3x/daycaller.git my-daycaller
cd my-daycaller
git remote set-url origin https://github.com/YOUR-USERNAME/YOUR-REPO.git
git push -u origin main
```

### 2. Add your reminders

Remove the examples and add your own. Times use the 24-hour clock in the time zone you set in step 3.

```bash
python daycaller.py remove 1 2 3
python daycaller.py add 06:30 "Your first class is at 8:30 in Room 101." --days mon,wed,fri
python daycaller.py add 07:00 "Your first class is at 9 in Hall B." --days tue,thu
python daycaller.py list
```

This updates `schedule.json`, which looks like this:

```json
{
  "next_id": 5,
  "reminders": [
    {
      "id": 4,
      "time": "06:30",
      "message": "Your first class is at 8:30 in Room 101.",
      "days": ["mon", "wed", "fri"]
    }
  ]
}
```

### 3. Set your time zone

In `.github/workflows/reminder-calls.yml`, change `TZ` to your [time zone name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones), for example `Africa/Dar_es_Salaam` or `Europe/London`. Then upload your changes:

```bash
git add schedule.json .github/workflows/reminder-calls.yml
git commit -m "Add my schedule"
git push
```

Run those three commands again whenever you change your reminders.

### 4. Add your Twilio secrets

In your repository, open **Settings → Secrets and variables → Actions → New repository secret** and add:

| Name | Value |
|---|---|
| `TWILIO_ACCOUNT_SID` | Your Account SID |
| `TWILIO_AUTH_TOKEN` | Your Auth Token |
| `TWILIO_FROM` | Your Twilio number |
| `MY_PHONE` | Your mobile number |

Never put these values in a file you commit.

### 5. Test a call

Open the **Actions** tab. If GitHub asks, enable workflows. Choose **Reminder calls → Run workflow**, then press any key on your phone when the call asks.

### 6. Set up the on-time trigger

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

## Troubleshooting

| Problem | What to do |
|---|---|
| `python` is not recognized | Open a new terminal. If it still fails, reinstall Python with **Add python.exe to PATH** ticked, or try `py` instead of `python`. |
| The PC doesn't ring | Keep the `python daycaller.py run` window open and stop the PC from sleeping. |
| Twilio says the number is unverified | Add your mobile under **Verified Caller IDs**, or upgrade the account. |
| Twilio says calling that country isn't allowed | Enable the country under **Voice → Settings → Geo Permissions**. |
| cron-job.org test shows `401` | The token was rejected. Use **HTTP authentication** with your GitHub username and token, and remove any `Authorization` header. |
| cron-job.org test shows `403` or `404` | Check the URL. Give the token access to this repository with **Contents: Read and write**. |
| Opening the dispatch URL in a browser shows `404` | This is normal. The URL only works as a `POST` with your token, so test it from cron-job.org. |
| The Actions run says `No reminders due` | Check `TZ`, the day and the time in `schedule.json`. The job must start within 90 minutes before the reminder. |
| No run appears in **Actions** | Enable workflows in the Actions tab, and make sure the workflow file is on your default branch. |
| Twilio says `completed`, but your phone never rang | A carrier or voicemail probably answered. Check Do Not Disturb, blocked and spam calls, and call forwarding. Save your Twilio number as a contact. |
| You keep getting called back | Press a key **after** you hear "Press any key to confirm". |

To see what happened to a call, open **Actions**, choose the latest run, and read the lines that start with `Attempt`. The Twilio Console also lists every call under **Monitor → Logs → Calls**.

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
