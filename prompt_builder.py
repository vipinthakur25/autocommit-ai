SYSTEM_INSTRUCTIONS = """\
You are an expert Android developer writing git commit messages.

CRITICAL RULES:
1. Read ALL files listed below before writing anything.
2. Your message MUST reflect the combined intent of ALL changes, not just one file.
3. Output ONLY the commit message — no explanation, no preamble, no trailing period.
4. If multiple files work together, describe what they achieve TOGETHER.

Follow the Conventional Commits format exactly:
  <type>(<scope>): <short description>

Allowed types : feat, fix, refactor, chore, docs, style, test, perf
Scope         : the feature or module these files belong to (e.g. auth, home, user)
Description   : present tense, lowercase, max 60 characters

Good examples for multiple files:
  feat(user): add DataUser model and state management in ViewModel
  feat(auth): add login request model and AuthViewModel flow
  refactor(home): extract data class and update ViewModel state

BAD (only mentions one file — never do this):
  feat(ui): introduce testingviewmodel class
"""


def _section_header(filepath, tier):
    """Format a readable section header for each file in the prompt."""
    tier_labels = {
        "full":    "FULL DIFF",
        "version": "VERSION CHANGES ONLY",
        "stats":   "STATS ONLY",
    }
    label = tier_labels.get(tier, tier.upper())
    return f"\n### [{label}] {filepath}"


def build_prompt(tiered_files):
    """
    Assemble the final prompt string that will be sent to Gemma.

    tiered_files: list of (filepath, summary, tier) from summarizer.tier_files()
    """
    if not tiered_files:
        return SYSTEM_INSTRUCTIONS + "\n\nNo meaningful changes detected."

    sections = [SYSTEM_INSTRUCTIONS, "\n\n--- CHANGED FILES ---"]

    for filepath, summary, tier in tiered_files:
        sections.append(_section_header(filepath, tier))
        sections.append(summary)

    sections.append("\n--- END OF CHANGES ---\n")
    sections.append("Commit message:")

    return "\n".join(sections)