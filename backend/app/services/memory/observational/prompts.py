"""Observer and Reflector prompt templates for Observational Memory."""

from __future__ import annotations

OBSERVER_SYSTEM_PROMPT = """\
You are an Observation Agent that creates dense, structured memory records for an AI coding assistant.

You will receive:
- EXISTING OBSERVATIONS (if any): the current observation log
- NEW MESSAGES: recent conversation messages not yet observed

Your task is to update or create the observation log to include the new messages.

## Output Format

Use this exact structure:

Date: <today's date, e.g. "February 19, 2026">

🔴 **Critical** (must never be lost):
- Item description
  - Supporting detail or file path

🟡 **Important** (key decisions, tool results, current state):
- Item description
  - Supporting detail

🟢 **Background** (context, resolved issues, preferences):
- Item description

<current-task>
One sentence describing exactly what the agent is working on right now.
</current-task>

<suggested-response>
One or two sentences the agent should use to continue naturally, e.g. "Continue implementing the JWT validation middleware in auth/middleware.py starting at the validateToken function."
</suggested-response>

## Rules

1. **Preserve ALL specifics verbatim**: file paths, function names, error messages, variable names, line numbers
2. **Priority assignment**:
   - 🔴 Critical: Unresolved errors, blocking issues, user's explicit constraints ("never do X"), security concerns
   - 🟡 Important: Completed tool results, key architectural decisions, current implementation state, recent file edits
   - 🟢 Background: Resolved problems, general context, project overview, preferences
3. **When merging with existing observations**: add new items, promote items if their status changed, demote resolved issues to 🟢
4. **Temporal anchoring**: Note dates for time-sensitive info ("as of Feb 19", "2 hours ago")
5. **Compression target**: 3-6x compression vs raw messages while retaining all actionable details
6. **Two-level bullets**: top level = event/task/decision, sub-bullets = file paths, values, specifics
7. **Do NOT include** conversation pleasantries, redundant clarifications, or information that has been superseded
"""

OBSERVER_USER_TEMPLATE = """\
{existing_observations_section}
{prior_chunks_section}
## New Messages to Observe

{new_messages_text}

---

Generate updated observations incorporating all new messages. Maintain the exact output format specified.\
"""

REFLECTOR_SYSTEM_PROMPT = """\
You are a Reflection Agent that condenses and restructures an existing observation log for an AI coding assistant.

The observation log has grown too large. Your task is to restructure it to be more compact while preserving all critical information.

## Compression Rules

1. **NEVER drop** 🔴 Critical items unless they are explicitly resolved (then move to 🟢 with resolution note)
2. **Merge related items**: combine 3 similar tool results into one bullet with sub-bullets
3. **Drop superseded info**: if a bug was fixed, keep only the fix, not the original bug report
4. **Keep temporal anchors**: preserve dates and time references for important events
5. **Preserve ALL specifics verbatim**: file paths, function names, error messages
6. **Restructure**: reorganize bullets by theme/component rather than chronological order
7. **Target**: reduce token count by 40-60% while retaining all 🔴 and 🟡 items

## Output Format

Use the same format as the input:

Date: <date>

🔴 **Critical**:
- ...

🟡 **Important**:
- ...

🟢 **Background**:
- ...

<current-task>
...
</current-task>

<suggested-response>
...
</suggested-response>
"""

REFLECTOR_USER_TEMPLATE = """\
## Current Observation Log (too large, needs compression)

{observation_content}

---

Restructure and compress the above observations. Target: reduce by 40-60% while preserving all 🔴 Critical items and all specific details (file paths, function names, error messages).\
"""

OBSERVATION_CONTINUATION_HINT = (
    "This message is not from the user. Conversation history was compacted into "
    "<observations> due to context limits. Continue naturally from prior context. "
    "Do not greet as if this is a new conversation."
)


def build_observer_prompt(
    existing_observation: str | None,
    new_messages: list[dict],
    today: str,
    prior_chunks: list[str] | None = None,
) -> list[dict]:
    """Build the Observer prompt messages list."""
    if existing_observation:
        existing_section = (
            f"## Existing Observations\n\n{existing_observation}\n"
        )
    else:
        existing_section = "## Existing Observations\n\n(none — this is the first observation)\n"

    # Build prior chunks section for dedup context
    if prior_chunks:
        chunk_parts = []
        for i, chunk_text in enumerate(prior_chunks, 1):
            chunk_parts.append(f"### Prior Chunk {i}\n{chunk_text}")
        prior_section = (
            "## Recent Observation Chunks (for reference — DO NOT repeat)\n\n"
            "The following chunks were recently generated from earlier messages in this "
            "conversation. Use them ONLY as context to avoid duplicating information. "
            "Do NOT restate facts, decisions, or details already captured below.\n\n"
            + "\n\n".join(chunk_parts)
            + "\n"
        )
    else:
        prior_section = ""

    new_messages_lines = []
    for msg in new_messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, list):
            import json
            content = json.dumps(content)
        new_messages_lines.append(f"[{role}]: {content}")

    user_content = OBSERVER_USER_TEMPLATE.format(
        existing_observations_section=existing_section,
        prior_chunks_section=prior_section,
        new_messages_text="\n\n".join(new_messages_lines),
    )
    user_content = f"Today's date: {today}\n\n" + user_content

    return [
        {"role": "system", "content": OBSERVER_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_reflector_prompt(observation_content: str) -> list[dict]:
    """Build the Reflector prompt messages list."""
    user_content = REFLECTOR_USER_TEMPLATE.format(
        observation_content=observation_content,
    )
    return [
        {"role": "system", "content": REFLECTOR_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def parse_observation_output(raw: str) -> tuple[str, str | None, str | None]:
    """
    Parse Observer/Reflector output into (content, current_task, suggested_response).

    Strips <current-task> and <suggested-response> XML tags from the content
    and returns them separately.
    """
    import re

    current_task: str | None = None
    suggested_response: str | None = None

    ct_match = re.search(r"<current-task>\s*(.*?)\s*</current-task>", raw, re.DOTALL)
    if ct_match:
        current_task = ct_match.group(1).strip()

    sr_match = re.search(r"<suggested-response>\s*(.*?)\s*</suggested-response>", raw, re.DOTALL)
    if sr_match:
        suggested_response = sr_match.group(1).strip()

    # Remove the XML sections from the main content
    content = re.sub(r"<current-task>.*?</current-task>", "", raw, flags=re.DOTALL)
    content = re.sub(r"<suggested-response>.*?</suggested-response>", "", content, flags=re.DOTALL)
    content = content.strip()

    return content, current_task, suggested_response
