"""
Detect Jira-style ticket IDs (e.g. PROJ-123, ABC-4567) from the
current git branch name.

Supported branch patterns:
    feature/PROJ-123-add-login          → PROJ-123
    PROJ-123/add-login                  → PROJ-123
    PROJ-123-add-login                  → PROJ-123
    bugfix/AUTH-99-fix-token            → AUTH-99
    PROJ-123                            → PROJ-123

Returns None if no Jira ticket pattern is found, which is fine —
the user opted into "no Jira yet" but this is future-proof.
"""

import re
import subprocess

# Match 2-10 uppercase letters, hyphen, 1-6 digits.
# Anchored to word boundaries so it won't grab from inside random text.
JIRA_REGEX = re.compile(r"\b([A-Z]{2,10}-\d{1,6})\b")


def get_current_branch():
    """Return the current git branch name, or None on error."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def detect_jira_ticket(branch_name=None):
    """
    Extract a Jira ticket ID from the given branch name.
    If branch_name is None, reads the current branch.

    Returns the ticket string (e.g. 'PROJ-123') or None.
    """
    if branch_name is None:
        branch_name = get_current_branch()

    if not branch_name:
        return None

    # Normalise: branches may be lowercase, but Jira IDs need uppercase
    # Match against the original first, then try uppercased version
    match = JIRA_REGEX.search(branch_name)
    if match:
        return match.group(1)

    # Try uppercased — handles branches like "feature/proj-123-foo"
    match = JIRA_REGEX.search(branch_name.upper())
    if match:
        return match.group(1)

    return None


def prefix_message_with_ticket(message, ticket):
    """
    Insert the Jira ticket into a commit message at the right place.

    Input :  feat(auth): add login flow
    Output:  feat(auth): [PROJ-123] add login flow

    If the message already contains the ticket, return it unchanged.
    """
    if not ticket or ticket in message:
        return message

    # Find the colon that separates type(scope) from description
    if ": " in message:
        prefix, desc = message.split(": ", 1)
        return f"{prefix}: [{ticket}] {desc}"

    # Fallback: prepend the ticket
    return f"[{ticket}] {message}"