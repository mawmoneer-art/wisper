# Outbound meeting-confirmation agent, build runbook

Working order, as agreed. Status is updated as we go.

| Step | What | Status |
|------|------|--------|
| 1 | Dashboard orientation (account exists, free tier) | in progress |
| 2 | Assistant with prompt, tested on a web call | next |
| 3 | Twilio number, import into Vapi, UAE geo permissions | pending |
| 4 | Call own mobile, iterate on wording | pending |
| 5 | Google Apps Script for calendar booking and outcome sheet, wired as book_meeting | pending |
| 6 | Trigger script: name, number, time, brief as variables | pending |

## Decisions so far

- Outcome record uses a Vapi structured output (post-call, cannot be skipped) instead of a log_outcome tool. Schema in `agent/outcome-schema.json`.
- book_meeting will be a Google Apps Script web app owned by the personal Gmail account. No hosted server, no OAuth client to configure.
- First message is hard-coded for the AI disclosure. Prompt in `agent/system-prompt.md`, first message in `agent/first-message.txt`, voicemail line in `agent/voicemail-message.txt`.
- Times are pre-formatted in words by the trigger script and passed as `{{when_spoken}}`.

## Known risks to test

- Foreign caller ID (US Twilio number) to UAE mobiles may be flagged or dropped by du and Etisalat. Tested at step 4.
- Free tier: web calls work now; phone import and outbound calls will need a payment method on the Vapi account and a funded Twilio account.
- Business hours only, Gulf time. Transactional call to a known contact, with AI disclosure. Do not reuse for people who did not agree to meet.
