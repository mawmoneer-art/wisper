# wisper

An outbound voice agent, built on Vapi, that phones a contact, confirms a
meeting, and writes it to Google Calendar once they say yes. Every call ends
with a structured outcome logged to a Google Sheet.

Start with `docs/RUNBOOK.md`. It has the build order and exact clicks.

- `agent/` the prompt, opening line, voicemail line, outcome schema
- `scripts/` `vapi_setup.py` builds the assistant, `call.py` places a call
- `apps-script/` the Google Apps Script that books the event and logs the call
- `docs/vapi/` a local snapshot of Vapi's documentation and API spec
