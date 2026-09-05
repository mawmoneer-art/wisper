# Outbound meeting-confirmation agent, build runbook

Working order, as agreed. One step at a time. Say "done" after each and we move on.

| Step | What | Status |
|------|------|--------|
| 0 | One-time Mac setup: API key, .env, Python check | next |
| 1 | Dashboard orientation | done |
| 2 | Assistant with prompt, tested on a web call | ready to run |
| 3 | Twilio number, import into Vapi, UAE geo permissions | written, pending |
| 4 | Call own mobile, iterate on wording | written, pending |
| 5 | Google Apps Script for calendar and outcome sheet, wired as book_meeting | written, pending |
| 6 | Trigger script: name, number, time, brief as variables | written, pending |

What is in this repo

| Path | Purpose |
|------|---------|
| `agent/system-prompt.md` | The assistant's instructions. Edit wording here. |
| `agent/first-message.txt` | The hard-coded opening line with the AI disclosure. |
| `agent/voicemail-message.txt` | What it says to an answering machine. |
| `agent/outcome-schema.json` | The structured outcome extracted after every call. |
| `agent/test-values.json` | Sample values used by the web-test copy of the assistant. |
| `agent/PROMPT-CHANGES.md` | What changed from your draft prompt and why. |
| `scripts/vapi_setup.py` | Creates or updates the assistant on Vapi. Re-run after any edit. |
| `scripts/call.py` | Places one call with name, number, time, location, brief. |
| `apps-script/Code.gs` | Google Apps Script: books the calendar event, logs each call to a Sheet. |
| `.env.example` | Template for your private settings. Copy to `.env`. |

---

## Step 0: one-time Mac setup

1. Download this repo. On the GitHub page for the branch, click the green **Code** button, then **Download ZIP**. Unzip it. Move the folder somewhere sensible, for example your Documents folder, and rename it `wisper` if it has a longer name.
2. Open **Terminal** (press Cmd+Space, type Terminal, press Enter).
3. Type `cd ` with a space after it, then drag the `wisper` folder from Finder into the Terminal window. Press Enter. The prompt now shows you are inside the folder.
4. Type `python3 --version` and press Enter. If you see a version number, good. If a window pops up offering to install command line tools, click **Install**, wait for it, then run the command again.
5. Get your Vapi API key. In the dashboard, open your organisation settings (bottom-left menu), find **API Keys**, and copy the private key. It starts with a long string of letters and numbers. Treat it like a password.
6. In Finder, inside the `wisper` folder, duplicate `.env.example` and rename the copy to `.env` (Finder will warn about the leading dot, confirm it). Open `.env` in TextEdit and fill in `VAPI_API_KEY=` and `MY_NAME=`. Leave the other two blank for now. Save.

Done when: `python3 --version` prints a version and `.env` has your key and name.

## Step 2: build the assistant and hear it

1. In Terminal, inside the folder:
   ```
   python3 scripts/vapi_setup.py
   ```
   It creates two assistants on your Vapi account and prints two links. "Meeting Confirmer" is the real one, with `{{placeholders}}` for name, time and brief. "Meeting Confirmer (web test)" is the same thing with sample values filled in, so you can talk to it from the dashboard.
2. Open the web-test link. Click **Talk** (top right). Allow the microphone. Answer the phone as Sarah. Try each path: say yes, say you'd prefer Thursday, say no, ask if it is a robot, ask to speak to Moneer, say wrong number.
3. Listen for three things: does the brief sound like a person talking, is the time said naturally, does it hang up promptly after each ending.
4. To change wording: edit `agent/system-prompt.md` (or the first message, or the sample values) in TextEdit, save, run `python3 scripts/vapi_setup.py` again, click Talk again. That's the loop. Voice, speed and transcriber can be changed in the dashboard on the web-test assistant without re-running anything, and when you like a setting, tell me and I'll pin it in the script so the real assistant matches.

On a web call the book_meeting tool is not wired yet, so a yes will end with "Moneer will send the invite directly". That's expected until step 5.

Done when: you've heard all six paths and are happy with the wording.

## Step 3: a number that can dial the UAE

1. Go to twilio.com, create an account, verify your email and mobile. Twilio starts you on a trial; upgrade it (add a card, **Billing** in the console) because trial accounts can only call verified numbers and add a trial announcement to every call. Put in about 20 dollars; UAE mobile calls cost roughly a few cents per minute from a US number.
2. Buy a number. Console left menu: **Phone Numbers** > **Manage** > **Buy a number**. Country: United States. Capabilities: tick **Voice**. Click **Search**, pick any number, click **Buy**. (A US number because it's instant. A UAE number needs a regulatory bundle and a week or more. We accept the foreign caller ID for now.)
3. Switch on international calling to the UAE. This is the part everyone gets stuck on. Console left menu: **Voice** > **Settings** > **Geo permissions** (Twilio sometimes lists it as **Voice Geographic Permissions**). Find **United Arab Emirates**, tick the box, and click **Save** at the bottom. If you skip this, every call fails silently with a "not permitted" error.
4. Copy your credentials. Console home page, **Account Info** panel: copy **Account SID** and click to reveal and copy **Auth Token**.
5. Import into Vapi. Dashboard > **Phone Numbers** > **Create Phone Number** > **Import Twilio**. Paste the number in international format (starting +1), the Account SID, the Auth Token. Label it "Twilio US". Click **Import from Twilio**.
6. Vapi will now ask for a payment method on your account if it hasn't already. Add one. Outbound calls are billed by the minute on Vapi as well as on Twilio.
7. Click the imported number in Vapi and copy its ID (a long string with dashes, shown on the number's page). Put it in `.env` as `PHONE_NUMBER_ID=`.

Done when: the number shows in Vapi's Phone Numbers list, UAE is ticked in Twilio geo permissions, and `.env` has the number ID.

## Step 4: call your own mobile

In Terminal:
```
python3 scripts/call.py --name "Your Name" --number "+9715XXXXXXXX" --when "2026-09-10 15:00" --duration 30 --location "your office" --brief "A test of the confirmation agent." --wait
```
Your phone rings within a few seconds. Answer, play the contact. When you hang up the script waits, then prints the outcome and note. Open the dashboard link it prints to hear the recording and read the transcript.

Things to check on this call, in order: does it connect at all (if not, geo permissions), what does the caller ID look like on your screen and is it labelled spam, is the delay before it speaks acceptable, does it talk over you. Try letting it go to voicemail once. Iterate wording with the step 2 loop; the real assistant is updated by the same command.

Done when: it sounds right on a real phone and voicemail behaves.

## Step 5: calendar booking and the outcome sheet

1. Go to sheets.google.com signed in as your personal Gmail. Create a blank spreadsheet. Name it "Agent calls".
2. In the spreadsheet menu: **Extensions** > **Apps Script**. A code editor opens with a file called Code.gs containing a stub.
3. Select everything in that editor, delete it, and paste the whole contents of `apps-script/Code.gs` from this repo.
4. Near the top, change `CHANGE_ME_TO_A_LONG_RANDOM_STRING` to a secret of your own, twenty or more random letters and digits. Keep it, you need it in step 6 below. Click the save icon.
5. In the toolbar, the function dropdown says `doPost`. Change it to **testBooking** and click **Run**. Google will ask you to authorise: click **Review permissions**, choose your account, click **Advanced**, then **Go to Untitled project (unsafe)** (it's your own script, this warning appears for anything not published by Google), then **Allow**. Check your calendar: a "TEST meeting from Vapi bridge" event appears for tomorrow at 3pm. Delete it. Check the spreadsheet: a "Calls" tab with headers appeared.
6. Deploy. Top right: **Deploy** > **New deployment**. Click the gear next to "Select type" and choose **Web app**. Description: "vapi bridge". Execute as: **Me**. Who has access: **Anyone**. Click **Deploy**. Copy the **Web app URL** (ends in `/exec`).
7. In `.env`, set `BOOK_MEETING_URL=` to that URL followed by `?key=` and your secret. Example shape: `https://script.google.com/macros/s/AKfy.../exec?key=yoursecret`.
8. In Terminal, run `python3 scripts/vapi_setup.py` again. It now attaches the book_meeting tool and end-of-call reporting to both assistants.
9. Open the web app URL in a browser tab. You should see "Vapi bridge is up." That confirms the deployment is public.

Any time you change Code.gs later, you must **Deploy** > **Manage deployments** > edit (pencil) > Version: **New version** > **Deploy**. Saving alone does not update the live URL.

Done when: a web test call where you say yes ends with "it's in the calendar", the event is on your calendar, and a row appears in the Sheet.

Known risk to test here: Apps Script answers POST requests with a redirect. Vapi should follow it. If the tool always reports failure even though the Sheet's Errors tab is empty, tell me and we swap the bridge to a small hosted function instead. That's a two-hour detour, not a redesign.

## Step 6: the trigger

Already built. This is the command:
```
python3 scripts/call.py --name "Sarah Khan" --number "+9715XXXXXXXX" --when "2026-09-16 15:00" --duration 30 --location "Marriott lobby cafe, Downtown Dubai" --brief "Walk through the regional expansion plan and hear your team's view." --email sarah@example.com --wait
```
Everything in quotes is yours to change. `--email` is optional and adds them as a guest so they get the invite. `--wait` keeps the script attached until the call ends and prints the outcome. Add `--dry-run` to see what it would send without calling.

Where to see results after each call: the "Agent calls" spreadsheet has one row per call with outcome, note, what they proposed, transcript and a link to the recording. The Vapi dashboard has the same under Calls.

---

## Decisions so far, one line each

- Outcome record is a post-call structured output, not a tool the model must remember. Alternative was a log_outcome webhook; rejected for reliability.
- book_meeting runs as a Google Apps Script web app inside your own Gmail. Alternative was a hosted server with Google OAuth; rejected for setup cost.
- First message is fixed text, so the AI disclosure cannot be paraphrased away. Alternative was letting the model open; rejected.
- Times are turned into spoken words by the trigger script, not by the model. Alternative was ISO timestamps in the prompt; rejected, models mangle timezones.
- Two assistants: real (templated) and web-test (sample values), both produced by one script. Alternative was one assistant with default values baked in; rejected because defaults could leak into real calls.
- Assistant built by script, tuned by editing a text file and re-running. Alternative was clicking through the dashboard; rejected because settings would drift between the test and real assistants.
- US Twilio number now, UAE number later if caller ID becomes a problem.

## Known risks

- Foreign caller ID (US Twilio number) to UAE mobiles may be flagged or dropped by du and Etisalat. Tested at step 4.
- Apps Script web apps answer POST with a redirect; if Vapi doesn't follow it, the tool needs a different host. Tested at step 5.
- Business hours only, Gulf time. Transactional call to a known contact with AI disclosure. Do not reuse for people who did not agree to meet; that becomes marketing under UAE rules.
- The model is gpt-4o at temperature 0.3, Vapi's default voice and transcriber. All swappable in the dashboard on the test assistant first.
