"""
Create and monitor a Devin session via the v3 API.

Usage:
    python run_session.py
"""

import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

# Ensure print output is flushed immediately (useful when piping / capturing)
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

load_dotenv()

API_BASE = "https://api.devin.ai"
API_KEY = os.environ["DEVIN_API_KEY"]

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


def get_self():
    """Verify the API key and print identity info."""
    resp = requests.get(f"{API_BASE}/v3/self", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def create_session(org_id: str, prompt: str, structured_output_schema: dict) -> dict:
    """Create a new Devin session that must return structured output."""
    resp = requests.post(
        f"{API_BASE}/v3/organizations/{org_id}/sessions",
        headers=HEADERS,
        json={
            "prompt": prompt,
            "structured_output_schema": structured_output_schema,
            "structured_output_required": True,
        },
    )
    resp.raise_for_status()
    return resp.json()


def terminate_session(org_id: str, session_id: str, archive: bool = False) -> dict:
    """Terminate a session so it stops running (optionally archiving it).

    History (messages, PRs, structured output) is preserved; the session
    simply moves to status 'exit' and cannot be resumed.
    """
    resp = requests.delete(
        f"{API_BASE}/v3/organizations/{org_id}/sessions/{session_id}",
        headers=HEADERS,
        params={"archive": str(archive).lower()},
    )
    resp.raise_for_status()
    return resp.json()


def get_session(org_id: str, session_id: str) -> dict:
    """Get the current status of a session."""
    resp = requests.get(
        f"{API_BASE}/v3/organizations/{org_id}/sessions/{session_id}",
        headers=HEADERS,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    # 1. Verify auth
    print("Verifying API key...")
    me = get_self()
    print(f"  Authenticated as: {me}")

    org_id = me.get("org_id")
    if not org_id:
        print("ERROR: Could not determine org_id from /v3/self response.")
        return

    # 2. Define the structured output we want back from the session
    structured_output_schema = {
        "type": "object",
        "properties": {
            "operands": {
                "type": "array",
                "items": {"type": "number"},
                "description": "The numbers that were added together.",
            },
            "expression": {
                "type": "string",
                "description": "The math expression as a string, e.g. '2 + 2'.",
            },
            "sum": {
                "type": "integer",
                "description": "The resulting sum.",
            },
            "file_created": {
                "type": "string",
                "description": "Name of the file created in the repo.",
            },
            "pr_url": {
                "type": "string",
                "description": "URL of the pull request that was opened.",
            },
            "summary": {
                "type": "string",
                "description": "A one-sentence summary of what was done.",
            },
        },
        "required": ["operands", "expression", "sum", "summary"],
    }

    # 3. Create session
    prompt = (
        "In the repo https://github.com/taylor-curran/orchestrate-devin-sessions, "
        "create a new Python file called math_result.py that computes 2 + 2 and "
        "prints the result. Then open a PR with your changes. "
        "When done, provide the structured output with the sum and related details."
    )
    print(f"\nCreating session in org {org_id}...")
    print(f"  Prompt: {prompt}")
    session = create_session(org_id, prompt, structured_output_schema)
    session_id = session["session_id"]
    print(f"  Session created: {session_id}")
    print(f"  URL: {session['url']}")
    print(f"  Status: {session['status']}")

    # 4. Poll until we get structured output (or the session ends)
    print("\nPolling session status (Ctrl+C to stop)...")
    prev_status = session["status"]
    try:
        while True:
            time.sleep(10)
            status = get_session(org_id, session_id)
            current = status["status"]
            detail = status.get("status_detail", "")
            if current != prev_status:
                print(f"  Status changed: {prev_status} -> {current} ({detail})")
                prev_status = current
            else:
                print(f"  Status: {current} ({detail})")

            structured = status.get("structured_output")
            if structured:
                print("\nStructured output received:")
                print(json.dumps(structured, indent=2))
                # 5. Terminate the session to free up the parallel slot
                print("\nTerminating session to free the parallel slot...")
                terminate_session(org_id, session_id)
                final = get_session(org_id, session_id)
                print(f"  Session terminated. Status: {final.get('status')}")
                break

            if current in ("exit", "error"):
                print(f"\nSession finished with status: {current}")
                break
    except KeyboardInterrupt:
        print("\nStopped polling.")

    print("\nDone.")


if __name__ == "__main__":
    main()
