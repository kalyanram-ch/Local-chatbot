"""
claude_client.py
-----------------
Two small, narrowly-scoped Claude API calls:

1. extract_keywords()  - turn a free-text user query into a few search
   keywords (e.g. "find my PAN card" -> ["PAN", "PAN card", "Permanent
   Account Number"]). No account data is sent for this call.

2. summarize_results()  - given ALREADY-REDACTED metadata (subjects,
   filenames, snippets with any ID/secret-looking text masked by
   redact.py), produce a short human summary pointing the user at the
   right link. The system prompt explicitly forbids repeating any
   number/secret-looking token even if one slipped through redaction.
"""

import os
import json
from anthropic import Anthropic

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set. See .env.example.")
        _client = Anthropic(api_key=api_key)
    return _client


def _extract_text(resp) -> str:
    """Pulls the text out of a Claude response. Response content can
    include non-text blocks first (e.g. a ThinkingBlock) — never assume
    content[0] is the text block, scan for the actual text block(s)."""
    parts = [block.text for block in resp.content if block.type == "text"]
    return "".join(parts).strip()


def extract_keywords(user_query: str) -> list[str]:
    client = _get_client()
    resp = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=200,
        system=(
            "You turn a user's short request into 2-5 search terms for "
            "searching their own Gmail/Drive by subject or filename. "
            "Include distinctive nouns as standalone terms (e.g. 'Aadhaar', "
            "'PAN') AND common real-world spelling variants of them (e.g. "
            "Aadhaar is very often written 'Aadhar' in India — include both "
            "spellings as separate terms). Avoid generic words alone that "
            "match far too much unrelated mail — 'card', 'ID', 'number', "
            "'document' should only appear as part of a specific phrase "
            "like 'Aadhaar card', never as a standalone term. "
            "Reply with ONLY a JSON array of strings, nothing else. "
            "Example: [\"Aadhaar\", \"Aadhar\", \"Aadhaar card\", \"Aadhar card\"]"
        ),
        messages=[{"role": "user", "content": user_query}],
    )
    text = _extract_text(resp)
    try:
        keywords = json.loads(text)
        if isinstance(keywords, list) and all(isinstance(k, str) for k in keywords):
            return keywords[:5]
    except (json.JSONDecodeError, IndexError):
        pass
    # Fallback: just use the raw query as a single keyword.
    return [user_query]


_SUMMARY_SYSTEM_PROMPT = """\
You help a user locate their own documents/emails in Gmail and Drive.

You are given a JSON array of search results, each with an "index". Every
snippet/filename in that array has ALREADY been redacted of ID numbers,
card numbers, passwords, and similar secrets (masked as [REDACTED-...]).
The underlying search is a loose full-text match, so it often includes
results that share a common word but are NOT actually what the user
asked for (e.g. an insurance "e-card" email when they asked for their
Aadhaar card) — your job is to separate genuine matches from noise.

Rules, no exceptions:
- NEVER output any sequence of digits longer than 3, and never output
  anything that looks like an ID number, account number, password, PIN,
  or OTP, even if you believe you see one in the input — treat any such
  token as [REDACTED] and do not repeat it.
- Do not guess or reconstruct a redacted value.
- Keep the reply short: 1-3 sentences. Don't repeat raw links, the app
  shows those separately.
- If nothing genuinely matches, say so plainly and return an empty list.

Reply with ONLY a JSON object, nothing else:
{"reply": "<your short summary>", "relevant_indices": [<the "index" values of results that genuinely match, most relevant first>]}
"""


def summarize_results(user_query: str, results: list[dict]) -> dict:
    """Returns {"reply": str, "relevant_indices": list[int]}. Falls back to
    treating every result as relevant if Claude's output can't be parsed —
    erring toward showing more, never toward silently hiding a real match."""
    indexed = [{"index": i, **r} for i, r in enumerate(results)]
    client = _get_client()
    resp = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=400,
        system=_SUMMARY_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"User's request: {user_query!r}\n\n"
                    f"Redacted search results (JSON): {json.dumps(indexed)}"
                ),
            }
        ],
    )
    text = _extract_text(resp)
    try:
        parsed = json.loads(text)
        reply = parsed.get("reply", "").strip()
        relevant = parsed.get("relevant_indices")
        if reply and isinstance(relevant, list):
            valid = {i for i in range(len(results))}
            return {"reply": reply, "relevant_indices": [i for i in relevant if i in valid]}
    except (json.JSONDecodeError, AttributeError):
        pass
    # Fallback: show everything rather than risk hiding a real match.
    return {"reply": text or "Here's what I found.", "relevant_indices": list(range(len(results)))}


_SHEET_SYSTEM_PROMPT = """\
You help a user understand a preview of their own Google Sheet.

You are given the sheet's name, its tab names, and a preview of rows from
one tab (as a JSON 2D array). Every cell has ALREADY been redacted of ID
numbers, account numbers, and secret-looking tokens (masked as
[REDACTED-...]).

Rules, no exceptions:
- NEVER output any sequence of digits longer than 3, and never output
  anything that looks like an ID number, account number, password, PIN,
  or OTP, even if you believe you can reconstruct one from context.
- Do not guess or reconstruct a redacted value.
- Answer the user's actual question about the sheet (e.g. "what's in it",
  "how many rows", "what are the column headers") using only the visible,
  non-redacted cell text.
- Keep the reply short and practical: a few sentences, or a tiny bullet
  list of column headers / notable rows if that's what's being asked.
- If the preview doesn't contain enough to answer, say so plainly and
  suggest opening the sheet link instead of guessing.

Reply with ONLY a JSON object, nothing else:
{"reply": "<your short answer>"}
"""


def summarize_sheet_preview(
    user_query: str, sheet_name: str, tab_names: list[str], rows: list[list[str]]
) -> str:
    """Given an already-redacted preview of one Sheet's rows, answers the
    user's question about its content. Returns plain reply text."""
    client = _get_client()
    resp = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=400,
        system=_SHEET_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"User's request: {user_query!r}\n\n"
                    f"Sheet name: {sheet_name!r}\n"
                    f"Tab names: {json.dumps(tab_names)}\n"
                    f"Redacted preview rows (JSON 2D array): {json.dumps(rows)}"
                ),
            }
        ],
    )
    text = _extract_text(resp)
    try:
        parsed = json.loads(text)
        reply = parsed.get("reply", "").strip()
        if reply:
            return reply
    except (json.JSONDecodeError, AttributeError):
        pass
    return text or "Here's a preview of that sheet."