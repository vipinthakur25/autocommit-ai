from diff_extractor import get_file_stats

# ── Token budget ────────────────────────────────────────────────────────────
# Gemma 1B / 4B context window = 8,192 tokens.
# We target a safe prompt size well under that limit.

MAX_PROMPT_TOKENS = 3000   # hard ceiling for the entire prompt
FULL_DIFF_BUDGET  = 2000   # tokens reserved for Tier-1 (full) diffs
CHARS_PER_TOKEN   = 4      # rough conversion: 1 token ≈ 4 English characters


def estimate_tokens(text):
    """Rough token estimate — good enough for budget tracking."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def _extract_version_lines(diff):
    """
    From a Gradle diff keep only lines that look like version changes.
    Strips noise while preserving the meaningful bump info.
    """
    result = []
    for line in diff.splitlines():
        low = line.lower()
        if any(kw in low for kw in ["version", "compilesdk", "minsdk",
                                     "targetsdk", "classpath", "plugin"]):
            result.append(line)
    return "\n".join(result[:20])  # cap at 20 lines


def _is_gradle(filepath):
    return filepath.endswith(".gradle") or filepath.endswith(".gradle.kts")


def _is_xml(filepath):
    return filepath.endswith(".xml")


def tier_files(ranked_files):
    """
    Apply 3-tier summarisation to a ranked list of (filepath, diff) tuples.

    Tier 1 — FULL diff      : high-value Kotlin/Java files (within budget)
    Tier 2 — VERSION lines  : Gradle files (only changed version lines)
    Tier 3 — STATS only     : XML, low-value, or budget-exhausted files

    Returns a list of (filepath, summary, tier_label) tuples.
    """
    result = []
    budget = FULL_DIFF_BUDGET  # remaining tokens for full diffs

    for filepath, diff in ranked_files:

        # ── Tier 2: Gradle files ────────────────────────────────────────────
        if _is_gradle(filepath):
            version_summary = _extract_version_lines(diff)
            if not version_summary.strip():
                adds, dels = get_file_stats(diff)
                version_summary = f"{adds} additions, {dels} deletions"
            result.append((filepath, version_summary, "version"))
            continue

        # ── Tier 3: XML resource files ──────────────────────────────────────
        if _is_xml(filepath):
            adds, dels = get_file_stats(diff)
            result.append((
                filepath,
                f"{adds} additions, {dels} deletions",
                "stats"
            ))
            continue

        # ── Tier 1 or Tier 3: Kotlin / Java ─────────────────────────────────
        token_cost = estimate_tokens(diff)

        if budget > 0:
            # Fit as much of the diff as the remaining budget allows
            char_limit = budget * CHARS_PER_TOKEN
            trimmed = diff[:char_limit]
            budget -= min(token_cost, budget)
            result.append((filepath, trimmed, "full"))
        else:
            # Budget exhausted — fall back to stats
            adds, dels = get_file_stats(diff)
            result.append((
                filepath,
                f"{adds} additions, {dels} deletions",
                "stats"
            ))

    return result


def total_prompt_tokens(tiered_files):
    """Return the estimated total token count for a list of tiered files."""
    return sum(estimate_tokens(summary) for _, summary, _ in tiered_files)
