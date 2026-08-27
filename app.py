"""
EIDIKO Chatbot — local, read-only Gmail/Drive document finder.

IMPORTANT SECURITY NOTES (read README.md for the full picture):
  - Runs locally on your machine only (127.0.0.1). Not deployed publicly.
  - Uses READ-ONLY Google scopes. It cannot send, delete, or modify anything.
  - It NEVER extracts or displays PAN/Aadhaar numbers, passwords, PINs,
    OTPs, or similar secrets — only links to the email/file that contains
    them, which you open yourself in Gmail/Drive.
  - Any queries containing words like "password", "otp", "cvv", "pin",
    "private key", "api key" are refused outright — see redact.py.
"""
import re
from datetime import datetime, timedelta, timezone
import os
from flask import Flask, request, jsonify, render_template, url_for
from dotenv import load_dotenv
import claude_client
from redact import redact, is_blocked_query

import google_client
import claude_client
from redact import redact, is_blocked_query

load_dotenv()

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    return jsonify({"authenticated": google_client.is_authenticated()})


@app.route("/api/authorize")
def authorize():
    """Non-blocking: returns a Google sign-in URL for the browser to open
    in a new tab. Does NOT wait for the user to complete sign-in — see
    /oauth2callback, which Google redirects back to when they're done."""
    try:
        redirect_uri = url_for("oauth2callback", _external=True)
        auth_url = google_client.build_auth_url(redirect_uri)
        return jsonify({"ok": True, "authUrl": auth_url})
    except FileNotFoundError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"Could not start Google sign-in: {e}"}), 500


@app.route("/oauth2callback")
def oauth2callback():
    """Google redirects here after the user approves (or cancels) access
    in the tab opened from /api/authorize. Runs as a normal, fast request
    — nothing in this app ever blocks a whole server thread on OAuth."""
    error = request.args.get("error")
    if error:
        return (
            f"<h3>Google sign-in was cancelled ({error}).</h3>"
            "<p>You can close this tab and click \"Connect Google Account\" again.</p>"
        )

    state = request.args.get("state", "")
    try:
        google_client.finish_auth_flow(state, request.url)
    except Exception as e:  # noqa: BLE001
        return f"<h3>Sign-in failed: {e}</h3><p>Close this tab and try again.</p>", 400

    return (
        "<h3>Google account connected ✅</h3>"
        "<p>Read-only access to Gmail and Drive granted. You can close this tab "
        "and go back to EIDIKO.</p>"
    )


@app.route("/api/disconnect", methods=["POST"])
def disconnect():
    google_client.disconnect()
    return jsonify({"ok": True})
def is_calendar_query(query: str) -> bool:
    """Detect whether the user is asking about Google Calendar."""

    calendar_words = [
        "calendar",
        "meeting",
        "meetings",
        "event",
        "events",
        "appointment",
        "appointments",
        "schedule",
        "scheduled",
        "festival",
        "festivals",
    ]

    query_lower = query.lower()

    return any(word in query_lower for word in calendar_words)
def get_calendar_range(query: str):
    """Return timeMin and timeMax for common calendar queries."""

    now = datetime.now().astimezone()

    query_lower = query.lower()

    # Today
    if "today" in query_lower:
        start = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        end = start + timedelta(days=1)

        return start.isoformat(), end.isoformat()

    # Tomorrow
    if "tomorrow" in query_lower:
        start = (
            now.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            + timedelta(days=1)
        )
        end = start + timedelta(days=1)

        return start.isoformat(), end.isoformat()

    # This week
    if "this week" in query_lower:
        start = (
            now
            - timedelta(days=now.weekday())
        ).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        end = start + timedelta(days=7)

        return start.isoformat(), end.isoformat()

    # This Friday
    if "friday" in query_lower:
        days_until_friday = (4 - now.weekday()) % 7

        start = (
            now.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            + timedelta(days=days_until_friday)
        )

        end = start + timedelta(days=1)

        return start.isoformat(), end.isoformat()

    # Default: next 7 days
    start = now
    end = now + timedelta(days=7)

    return start.isoformat(), end.isoformat()

def handle_calendar_query(creds, user_query):
    """Search Google Calendar and return formatted chatbot data."""

    time_min, time_max = get_calendar_range(user_query)

    events = google_client.search_calendar(
        creds,
        time_min,
        time_max,
    )

    # Optional keyword filtering for festival/event-related searches
    query_lower = user_query.lower()

    if "festival" in query_lower or "festivals" in query_lower:
        filtered = []

        for event in events:
            text = (
                event.get("summary", "")
                + " "
                + event.get("description", "")
            ).lower()

            if "festival" in text or "fest" in text:
                filtered.append(event)

        events = filtered

    if not events:
        return {
            "reply": "I couldn't find any matching events in your Google Calendar.",
            "results": [],
        }

    # Prepare safe data for Claude
    claude_payload = []

    for event in events:
        claude_payload.append(
            {
                "source": "calendar",
                "summary": redact(event.get("summary", "")),
                "description": redact(event.get("description", "")),
                "start": event.get("start", ""),
                "end": event.get("end", ""),
                "location": redact(event.get("location", "")),
            }
        )

    outcome = claude_client.summarize_results(
        user_query,
        claude_payload,
    )

    summary = redact(outcome["reply"])

    display_results = []

    for event in events:
        display_results.append(
            {
                "title": redact(event.get("summary", "(No title)")),
                "meta": redact(event.get("location", "")),
                "date": event.get("start", ""),
                "link": event.get("html_link", ""),
                "source": "calendar",
                "attachments": [],
            }
        )

    return {
        "reply": summary,
        "results": display_results,
    }


def is_meet_query(query: str) -> bool:
    """Detect whether the user is asking about Google Meet calls
    specifically, as opposed to calendar events in general. Uses a
    word-boundary check on "meet" so it doesn't false-positive on
    "meeting"/"meetings" (those stay routed to is_calendar_query)."""

    query_lower = query.lower()

    if re.search(r"\bmeet\b", query_lower):
        return True

    meet_phrases = ["google meet", "video call", "hangout", "join link", "meet link"]
    return any(phrase in query_lower for phrase in meet_phrases)


def handle_meet_query(creds, user_query):
    """Search Calendar for events in the relevant time range that have a
    Google Meet video link attached, and summarize just those."""

    time_min, time_max = get_calendar_range(user_query)

    events = google_client.search_calendar(creds, time_min, time_max)
    meet_events = [e for e in events if e.get("meet_link")]

    if not meet_events:
        return {
            "reply": "I couldn't find any upcoming Google Meet calls in that range.",
            "results": [],
        }

    claude_payload = []
    for event in meet_events:
        claude_payload.append(
            {
                "source": "meet",
                "summary": redact(event.get("summary", "")),
                "description": redact(event.get("description", "")),
                "start": event.get("start", ""),
                "end": event.get("end", ""),
            }
        )

    outcome = claude_client.summarize_results(user_query, claude_payload)
    summary = redact(outcome["reply"])

    display_results = [
        {
            "title": redact(event.get("summary", "(No title)")),
            "meta": "Google Meet",
            "date": event.get("start", ""),
            "link": event.get("meet_link", ""),
            "source": "meet",
            "attachments": [],
        }
        for event in meet_events
    ]

    return {
        "reply": summary,
        "results": display_results,
    }


def is_sheets_query(query: str) -> bool:
    """Detect whether the user is asking about a Google Sheet/spreadsheet."""

    sheet_words = ["sheet", "sheets", "spreadsheet", "excel"]
    query_lower = query.lower()
    return any(word in query_lower for word in sheet_words)


def wants_sheet_content(query: str) -> bool:
    """Within a sheets query, distinguish "find the file" (e.g. "find my
    budget sheet") from "show me what's in it" (e.g. "what's in my budget
    sheet", "read the rows", "show the data")."""

    content_words = [
        "read", "open", "what's in", "whats in", "what is in", "content",
        "data in", "values", "rows", "columns", "show me the data",
        "preview", "inside",
    ]
    query_lower = query.lower()
    return any(word in query_lower for word in content_words)


def handle_sheets_query(creds, user_query, keywords):
    """Find matching Google Sheets by name; if the user seems to want the
    actual content, also fetch a small, redacted preview of the top match's
    first tab and have Claude answer against that preview."""

    sheet_results = google_client.search_sheets(creds, keywords)
    for r in sheet_results:
        r["name"] = redact(r["name"])

    if not sheet_results:
        return {
            "reply": "I couldn't find any matching spreadsheet in your Drive.",
            "results": [],
        }

    if not wants_sheet_content(user_query):
        # Find-only: same shape as a Drive result card, no content read.
        claude_payload = [
            {k: v for k, v in r.items() if k not in ("id",)} for r in sheet_results
        ]
        outcome = claude_client.summarize_results(user_query, claude_payload)
        summary = redact(outcome["reply"])

        # Unlike the combined Gmail/Drive search, we deliberately do NOT
        # filter sheet_results down to outcome["relevant_indices"] here.
        # That filter exists because Gmail/Drive's underlying search is
        # loose full-text matching that can pull in unrelated results
        # (see the comment in /api/chat). Sheets search above already
        # matches on filename tokens only, so it's precise by construction
        # — and summarize_results' prompt is written for "Gmail and
        # Drive" specifically, so it doesn't reliably recognize a
        # "sheets" source as relevant, which was silently dropping every
        # genuine match's link even though the reply text said "found
        # it". Show everything search_sheets found, same as the
        # Calendar/Meet handlers already do.
        display_results = [
            {
                "title": r["name"],
                "meta": "Google Sheet",
                "date": r.get("modified", ""),
                "link": r["link"],
                "source": "sheets",
                "attachments": [],
            }
            for r in sheet_results
        ]
        return {"reply": summary, "results": display_results}

    # Content preview: read the single best-matching sheet's first tab.
    top = sheet_results[0]
    try:
        tab_names = google_client.get_sheet_tab_names(creds, top["id"])
        first_tab = tab_names[0] if tab_names else "Sheet1"
        # Small, bounded preview — enough to answer "what's in this" /
        # "what are the columns" without pulling a whole large sheet.
        raw_rows = google_client.get_sheet_values(creds, top["id"], f"'{first_tab}'!A1:J50")
    except Exception as e:  # noqa: BLE001
        return {
            "reply": f"I found \"{top['name']}\" but couldn't read its contents: {e}",
            "results": [
                {
                    "title": top["name"],
                    "meta": "Google Sheet",
                    "date": top.get("modified", ""),
                    "link": top["link"],
                    "source": "sheets",
                    "attachments": [],
                }
            ],
        }

    # Redact every cell before it goes anywhere (display or Claude) — same
    # rule as every other data source in this app.
    redacted_rows = [[redact(str(cell)) for cell in row] for row in raw_rows]

    reply = claude_client.summarize_sheet_preview(
        user_query, top["name"], tab_names, redacted_rows
    )
    reply = redact(reply)

    return {
        "reply": reply,
        "results": [
            {
                "title": top["name"],
                "meta": "Google Sheet",
                "date": top.get("modified", ""),
                "link": top["link"],
                "source": "sheets",
                "attachments": [],
            }
        ],
    }


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True) or {}
    user_query = (data.get("message") or "").strip()

    if not user_query:
        return jsonify({"reply": "Ask me something like \"find my PAN card\" or \"find my Aadhaar\".", "results": []})

    # Hard refusal for password/secret-style requests — no search is run.
    if is_blocked_query(user_query):
        return jsonify(
            {
                "reply": (
                    "I won't search for or return passwords, PINs, OTPs, or similar "
                    "secrets — that's exactly the kind of data an account-takeover tool "
                    "goes after, so it's out of scope here by design. If you have "
                    "passwords sitting in old emails, please delete those emails and "
                    "move to a password manager instead."
                ),
                "results": [],
            }
        )

    creds = google_client.get_credentials()
    if creds is None:
        return jsonify(
            {
                "reply": "Your Google account isn't connected yet. Click \"Connect Google Account\" above first.",
                "results": [],
            }
        )

    if is_meet_query(user_query):
        try:
            result = handle_meet_query(creds, user_query)
            return jsonify(result)
        except Exception as e:
            return jsonify(
                {
                    "reply": f"Meet search failed: {e}",
                    "results": [],
                }
            ), 500

    if is_calendar_query(user_query):
        try:
            result = handle_calendar_query(creds, user_query)
            return jsonify(result)
        except Exception as e:
            return jsonify(
            {
                "reply": f"Calendar search failed: {e}",
                "results": [],
            }
        ), 500

    try:
        keywords = claude_client.extract_keywords(user_query)
    except RuntimeError as e:
        return jsonify({"reply": str(e), "results": []}), 400

    if is_sheets_query(user_query):
        try:
            result = handle_sheets_query(creds, user_query, keywords)
            return jsonify(result)
        except Exception as e:
            return jsonify(
                {
                    "reply": f"Sheets search failed: {e}",
                    "results": [],
                }
            ), 500

    gmail_results = google_client.search_gmail(creds, keywords)
    drive_results = google_client.search_drive(creds, keywords)

    
    # Redact BEFORE anything leaves this function — both for what's shown
    # to the user and what's sent to the Claude API for summarization.
    for r in gmail_results:
        r["subject"] = redact(r["subject"])
        r["snippet"] = redact(r["snippet"])
        for a in r.get("attachments", []):
            a["filename"] = redact(a["filename"])
    for r in drive_results:
        r["name"] = redact(r["name"])

    combined = gmail_results + drive_results

    if not combined:
        return jsonify({"reply": "I couldn't find anything matching that in your Gmail or Drive.", "results": []})

    # Claude only ever sees redacted subjects/snippets/filenames for
    # ranking/summarizing — never attachment ids/bytes, never raw content.
    claude_payload = [
        {k: v for k, v in r.items() if k not in ("id", "attachments")} for r in combined
    ]
    outcome = claude_client.summarize_results(user_query, claude_payload)

    # Final belt-and-suspenders redaction pass on the model's own output.
    summary = redact(outcome["reply"])

    # Only show the results Claude judged as genuine matches — the
    # underlying Gmail/Drive search is loose full-text matching, so
    # "find my Aadhaar" can otherwise surface an unrelated "insurance
    # e-card" email just because both contain the word "card".
    relevant = [combined[i] for i in outcome["relevant_indices"]]

    display_results = [
        {
            "title": r.get("subject") or r.get("name"),
            "meta": r.get("from") or r.get("mime_type", ""),
            "date": r.get("date") or r.get("modified", ""),
            "link": r["link"],
            "source": r["source"],
            "attachments": [
                {
                    "filename": a["filename"],
                    "download_url": (
                        f"/api/download?message_id={r['id']}&attachment_id={a['attachment_id']}"
                        f"&filename={a['filename']}"
                    ),
                }
                for a in r.get("attachments", [])
            ],
        }
        for r in relevant
    ]

    return jsonify({"reply": summary, "results": display_results})


@app.route("/api/download")
def download_attachment():
    """Streams one Gmail attachment straight from the Gmail API to the
    browser as a file download. The bytes pass through this process only
    — they are never parsed, stored on disk, or sent to the Claude API."""
    creds = google_client.get_credentials()
    if creds is None:
        return jsonify({"error": "Google account not connected."}), 401

    message_id = request.args.get("message_id", "")
    attachment_id = request.args.get("attachment_id", "")
    filename = request.args.get("filename") or "attachment"
    if not message_id or not attachment_id:
        return jsonify({"error": "Missing message_id or attachment_id."}), 400

    try:
        data = google_client.get_attachment_bytes(creds, message_id, attachment_id)
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": f"Couldn't fetch attachment: {e}"}), 500

    from werkzeug.utils import secure_filename
    from flask import Response

    safe_name = secure_filename(filename) or "attachment"
    return Response(
        data,
        mimetype="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # use_reloader=False: on some Windows Python installs (e.g. the
    # Microsoft Store package), the reloader's file-watcher spuriously
    # detects "changes" in stdlib files and restarts the process — which
    # kills in-flight requests like the blocking Google OAuth flow before
    # it can open a browser window.
    app.run(host="127.0.0.1", port=port, debug=True, use_reloader=False)