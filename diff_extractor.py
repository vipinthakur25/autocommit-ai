import subprocess


def get_staged_diff():
    """Get the raw staged diff from git."""
    result = subprocess.run(
        ["git", "diff", "--staged"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"git diff failed: {result.stderr}")
    return result.stdout


def split_by_file(raw_diff):
    """Split a raw diff string into a dict of {filepath: diff_content}."""
    files = {}
    current_file = None
    current_lines = []

    for line in raw_diff.splitlines():
        if line.startswith("diff --git"):
            # Save previous file
            if current_file:
                files[current_file] = "\n".join(current_lines)
            # Start new file — extract path from "diff --git a/path b/path"
            parts = line.split(" b/")
            current_file = parts[-1] if len(parts) > 1 else line
            current_lines = [line]
        elif current_file:
            current_lines.append(line)

    # Save last file
    if current_file and current_lines:
        files[current_file] = "\n".join(current_lines)

    return files


def get_file_stats(diff_content):
    """Return (additions, deletions) count for a diff."""
    additions = sum(1 for l in diff_content.splitlines() if l.startswith("+") and not l.startswith("+++"))
    deletions = sum(1 for l in diff_content.splitlines() if l.startswith("-") and not l.startswith("---"))
    return additions, deletions
