#!/usr/bin/env python3
"""Place one outbound meeting-confirmation call.

Example:
    python3 scripts/call.py \
        --name "Sarah Khan" \
        --number "+9715XXXXXXXX" \
        --when "2026-09-09 15:00" \
        --duration 30 \
        --location "Marriott lobby cafe, Downtown Dubai" \
        --brief "Walk through the regional expansion plan and hear your team's view." \
        --email sarah@example.com

Times are Gulf Standard Time (UTC+4). The script turns the time into spoken
words for the assistant and into ISO timestamps for the calendar.

Reads from .env: VAPI_API_KEY, MY_NAME, and PHONE_NUMBER_ID (the Vapi ID of the
imported Twilio number). Assistant ID comes from .vapi/state.json, written by
scripts/vapi_setup.py.

Add --wait to stay attached until the call ends and print the logged outcome.
Add --dry-run to print the request without placing a call.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vapi_common import api, load_env, load_state, require  # noqa: E402

GST = timezone(timedelta(hours=4), name="Asia/Dubai")

HOURS = ["twelve", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven"]
MINUTES = {
    0: "", 5: "five past", 10: "ten past", 15: "quarter past", 20: "twenty past", 25: "twenty five past",
    30: "half past", 35: "twenty five to", 40: "twenty to", 45: "quarter to", 50: "ten to", 55: "five to",
}
ORDINALS = {
    1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth",
    9: "ninth", 10: "tenth", 11: "eleventh", 12: "twelfth", 13: "thirteenth", 14: "fourteenth",
    15: "fifteenth", 16: "sixteenth", 17: "seventeenth", 18: "eighteenth", 19: "nineteenth",
    20: "twentieth", 21: "twenty first", 22: "twenty second", 23: "twenty third", 24: "twenty fourth",
    25: "twenty fifth", 26: "twenty sixth", 27: "twenty seventh", 28: "twenty eighth",
    29: "twenty ninth", 30: "thirtieth", 31: "thirty first",
}


TENS = {1: "ten", 2: "twenty", 3: "thirty", 4: "forty", 5: "fifty"}
ONES = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
TEENS = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]


def minute_words(m):
    if m < 10:
        return f"oh {ONES[m]}"
    if m < 20:
        return TEENS[m - 10]
    return (TENS[m // 10] + (" " + ONES[m % 10] if m % 10 else "")).strip()


def spoken_time(dt):
    """'Tuesday the ninth of September at three in the afternoon'."""
    h, m = dt.hour, dt.minute
    if m in MINUTES and m != 0:
        base_hour = h + 1 if m > 30 else h
        hour_word = HOURS[base_hour % 12]
        ref_hour = base_hour
    else:
        hour_word = HOURS[h % 12]
        ref_hour = h
    if ref_hour == 12 and m == 0:
        clock = "midday"
    elif ref_hour % 24 == 0 and m == 0:
        clock = "midnight"
    else:
        part = "in the morning" if ref_hour < 12 else "in the afternoon" if ref_hour < 17 else "in the evening"
        if m == 0:
            clock = f"{hour_word} {part}"
        elif m in MINUTES:
            clock = f"{MINUTES[m]} {hour_word} {part}"
        else:
            clock = f"{HOURS[h % 12]} {minute_words(m)} {part}"
    day = dt.strftime("%A")
    month = dt.strftime("%B")
    return f"{day} the {ORDINALS[dt.day]} of {month} at {clock}"


def parse_when(text):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=GST)
        except ValueError:
            continue
    print(f"Could not read the time '{text}'. Use YYYY-MM-DD HH:MM, for example 2026-09-09 15:00", file=sys.stderr)
    sys.exit(1)


def main():
    load_env()
    ap = argparse.ArgumentParser(description="Place an outbound meeting-confirmation call.")
    ap.add_argument("--name", required=True, help="Contact's name, as the assistant should say it")
    ap.add_argument("--number", required=True, help="Contact's mobile in international format, e.g. +9715XXXXXXXX")
    ap.add_argument("--when", required=True, help="Meeting start, Dubai time, e.g. '2026-09-09 15:00'")
    ap.add_argument("--duration", type=int, default=30, help="Minutes (default 30)")
    ap.add_argument("--location", required=True)
    ap.add_argument("--brief", required=True, help="What the meeting is about, in your own words")
    ap.add_argument("--email", default="", help="Contact's email, to add them as a calendar guest (optional)")
    ap.add_argument("--my-name", default=os.environ.get("MY_NAME", ""), help="Defaults to MY_NAME in .env")
    ap.add_argument("--title", default="", help="Calendar event title (default: 'Meeting with <name>')")
    ap.add_argument("--wait", action="store_true", help="Wait for the call to end and print the outcome")
    ap.add_argument("--dry-run", action="store_true", help="Show the request, do not call")
    args = ap.parse_args()

    if not args.my_name:
        print("Set MY_NAME in .env or pass --my-name", file=sys.stderr)
        sys.exit(1)
    if not args.number.startswith("+"):
        print("Number must start with + and the country code, e.g. +9715XXXXXXXX", file=sys.stderr)
        sys.exit(1)

    start = parse_when(args.when)
    if start < datetime.now(GST):
        print(f"That time ({start:%Y-%m-%d %H:%M} Dubai) is in the past. Stopping.", file=sys.stderr)
        sys.exit(1)
    if not (8 <= start.hour < 21):
        print("Warning: proposed meeting time is outside 8am to 9pm Dubai. Continuing.", file=sys.stderr)
    now = datetime.now(GST)
    if not (9 <= now.hour < 18) or now.weekday() >= 5:
        print("Warning: you are placing this call outside business hours in Dubai (Mon-Fri, 9am to 6pm).", file=sys.stderr)
    end = start + timedelta(minutes=args.duration)

    state = load_state()
    if args.dry_run:
        assistant_id = state.get("assistantId", "<run scripts/vapi_setup.py first>")
        phone_number_id = os.environ.get("PHONE_NUMBER_ID", "<set PHONE_NUMBER_ID in .env at step 3>")
    else:
        assistant_id = state.get("assistantId") or require("VAPI_ASSISTANT_ID", "Run scripts/vapi_setup.py first.")
        phone_number_id = require("PHONE_NUMBER_ID", "Set it in .env after importing the Twilio number (step 3).")

    variables = {
        "my_name": args.my_name,
        "contact_name": args.name,
        "when_spoken": spoken_time(start),
        "duration_minutes": str(args.duration),
        "location": args.location,
        "brief": args.brief,
        "start_iso": start.isoformat(),
        "end_iso": end.isoformat(),
        "title": args.title or f"Meeting with {args.name}",
        "attendee_email": args.email,
    }
    payload = {
        "assistantId": assistant_id,
        "phoneNumberId": phone_number_id,
        "customer": {"number": args.number, "name": args.name, **({"email": args.email} if args.email else {})},
        "assistantOverrides": {"variableValues": variables},
    }

    print(f"Calling {args.name} at {args.number}")
    print(f"Proposed: {variables['when_spoken']} ({args.duration} min) at {args.location}")
    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return

    call = api("POST", "/call", payload)
    call_id = call["id"]
    print(f"Call placed. id={call_id}")
    print(f"Watch it: https://dashboard.vapi.ai/calls/{call_id}")
    if not args.wait:
        return

    print("Waiting for the call to end", end="", flush=True)
    while True:
        time.sleep(5)
        call = api("GET", f"/call/{call_id}")
        status = call.get("status")
        if status == "ended":
            break
        print(".", end="", flush=True)
    print()
    print(f"Ended: {call.get('endedReason')}")
    outputs = (call.get("artifact") or {}).get("structuredOutputs") or {}
    outcome = None
    for value in outputs.values():
        result = value.get("result") if isinstance(value, dict) else None
        if isinstance(result, dict) and "outcome" in result:
            outcome = result
    if outcome:
        print(f"Outcome: {outcome.get('outcome')}")
        print(f"Note:    {outcome.get('note')}")
        if outcome.get("proposed_time_text"):
            print(f"They proposed: {outcome['proposed_time_text']}")
    else:
        print("Outcome not available yet. Check the Sheet or the dashboard in a minute.")
    summary = (call.get("analysis") or {}).get("summary")
    if summary:
        print(f"Summary: {summary}")


if __name__ == "__main__":
    main()
