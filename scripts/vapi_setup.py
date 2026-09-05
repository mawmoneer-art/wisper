#!/usr/bin/env python3
"""Create or update the meeting-confirmation assistant on Vapi.

Safe to run repeatedly. It finds existing objects by name and updates them,
so you can edit agent/system-prompt.md and re-run to push the new wording.

Reads from .env:
    VAPI_API_KEY        required
    BOOK_MEETING_URL    optional. The Apps Script web app URL (with ?key=...).
                        When set, the book_meeting tool and end-of-call
                        reporting are wired to it. Leave unset until step 5.

Usage:
    python3 scripts/vapi_setup.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vapi_common import ROOT, api, load_env, load_state, save_state  # noqa: E402

ASSISTANT_NAME = "Meeting Confirmer"
TEST_ASSISTANT_NAME = "Meeting Confirmer (web test)"
OUTPUT_NAME = "Meeting call outcome"
AGENT = ROOT / "agent"


def read(name):
    return (AGENT / name).read_text().strip()


def render(text, values):
    """Fill {{var}} placeholders with concrete values for the web-test copy."""
    import re
    return re.sub(r"{{\s*(\w+)\s*}}", lambda m: values.get(m.group(1), m.group(0)), text)


def find_by_name(path, name):
    items = api("GET", path) or []
    if isinstance(items, dict):
        items = items.get("results") or items.get("items") or []
    for item in items:
        if item.get("name") == name:
            return item
    return None


def upsert_structured_output():
    schema = json.loads(read("outcome-schema.json"))
    body = {
        "name": OUTPUT_NAME,
        "type": "ai",
        "description": "Final outcome of an outbound meeting-confirmation call, as the meeting owner needs it logged.",
        "schema": schema,
    }
    existing = find_by_name("/structured-output", OUTPUT_NAME)
    if existing:
        api("PATCH", f"/structured-output/{existing['id']}", {"schema": schema, "description": body["description"]})
        print(f"updated structured output {existing['id']}")
        return existing["id"]
    created = api("POST", "/structured-output", body)
    print(f"created structured output {created['id']}")
    return created["id"]


def book_meeting_tool(url):
    return {
        "type": "function",
        "async": False,
        "server": {"url": url, "timeoutSeconds": 20},
        "messages": [
            {"type": "request-start", "content": "Let me put that in the calendar."},
            {"type": "request-failed", "content": "I could not reach the calendar just now."},
        ],
        "function": {
            "name": "book_meeting",
            "description": "Create the meeting on the owner's Google Calendar. Call this only after the person has clearly said yes to the proposed time. All meeting details are already known; only pass the confirming person's name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmed_by": {
                        "type": "string",
                        "description": "Name of the person who confirmed, as they gave it.",
                    }
                },
                "required": ["confirmed_by"],
            },
        },
    }


def assistant_body(output_id, book_url, test_values=None):
    tools = [{"type": "endCall"}]
    if book_url:
        tools.append(book_meeting_tool(book_url))
    fill = (lambda t: render(t, test_values)) if test_values else (lambda t: t)
    body = {
        "name": TEST_ASSISTANT_NAME if test_values else ASSISTANT_NAME,
        "firstMessageMode": "assistant-speaks-first",
        "firstMessage": fill(read("first-message.txt")),
        "voicemailMessage": fill(read("voicemail-message.txt")),
        "voicemailDetection": {"provider": "vapi"},
        "model": {
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.3,
            "messages": [{"role": "system", "content": fill(read("system-prompt.md"))}],
            "tools": tools,
        },
        "maxDurationSeconds": 300,
        "artifactPlan": {"recordingEnabled": True, "structuredOutputIds": [output_id]},
        "metadata": {"managedBy": "scripts/vapi_setup.py"},
    }
    if book_url:
        body["server"] = {"url": book_url, "timeoutSeconds": 20}
        body["serverMessages"] = ["end-of-call-report"]
    return body


def main():
    load_env()
    import os
    book_url = os.environ.get("BOOK_MEETING_URL", "").strip() or None
    state = load_state()

    output_id = upsert_structured_output()
    test_values = json.loads(read("test-values.json"))

    def upsert_assistant(body):
        existing = find_by_name("/assistant", body["name"])
        if existing:
            result = api("PATCH", f"/assistant/{existing['id']}", body)
            print(f"updated assistant '{body['name']}' {result['id']}")
        else:
            result = api("POST", "/assistant", body)
            print(f"created assistant '{body['name']}' {result['id']}")
        return result

    assistant = upsert_assistant(assistant_body(output_id, book_url))
    test_assistant = upsert_assistant(assistant_body(output_id, book_url, test_values))

    state.update({
        "assistantId": assistant["id"],
        "testAssistantId": test_assistant["id"],
        "structuredOutputId": output_id,
    })
    save_state(state)
    print()
    print(f"Real assistant (templated, used by scripts/call.py): https://dashboard.vapi.ai/assistants/{assistant['id']}")
    print(f"Web-test assistant (sample values filled in):        https://dashboard.vapi.ai/assistants/{test_assistant['id']}")
    if book_url:
        print("book_meeting tool: wired to", book_url.split("?")[0])
    else:
        print("book_meeting tool: not wired yet (set BOOK_MEETING_URL in .env at step 5 and re-run)")
    print("Next: open the web-test assistant in the dashboard, press Talk, and have the conversation.")
    print("To change wording: edit files in agent/, re-run this script, press Talk again.")


if __name__ == "__main__":
    main()
