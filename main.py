#!/usr/bin/env python3
"""
AutoCommit AI -- local LLM commit message generator for Android projects.

Usage:
    python main.py                     # interactive mode
    python main.py --auto              # auto-commit without confirmation
    python main.py --model gemma3:4b   # use a different Ollama model
    python main.py --dry-run           # preview only, do not commit
    python main.py --no-scope          # disable scope auto-detection
    python main.py --no-jira           # disable Jira ticket prefix
    python main.py --install-hook      # install as git hook in current repo
    python main.py --uninstall-hook    # remove git hook from current repo

Requirements:
    pip install requests gitpython
    ollama pull gemma3:1b
"""

import sys
import os
import argparse
import requests
import shutil

from diff_extractor  import get_staged_diff, split_by_file
from filter          import filter_files
from scorer          import rank_files
from summarizer      import tier_files, total_prompt_tokens
from scope_detector  import detect_scope
from jira_detector   import detect_jira_ticket, prefix_message_with_ticket


# -- Config -------------------------------------------------------------------

OLLAMA_URL      = "http://localhost:11434/api/generate"
DEFAULT_MODEL   = "gemma3:1b"
MAX_SAFE_TOKENS = 3000


# -- Gemma caller -------------------------------------------------------------

def call_gemma(prompt, model=DEFAULT_MODEL, max_tokens=80):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model":  model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": max_tokens,
                },
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["response"].strip()

    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Cannot reach Ollama at localhost:11434")
        print("        Start it with:  ollama serve")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("\n[ERROR] Ollama timed out. Try gemma3:1b for speed.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Ollama error: {e}")
        sys.exit(1)


# -- Two-pass commit message generator ---------------------------------------

def generate_commit_message(tiered_files, model=DEFAULT_MODEL, scope_hint=None,
                            verbose=True):
    summaries = []

    if verbose:
        print("-> Pass 1: reading each file...")

    for filepath, diff, tier in tiered_files:
        filename = filepath.split("/")[-1].split("\\")[-1]

        if tier == "stats":
            summaries.append(f"- {filename}: {diff}")
            if verbose:
                print(f"    o {filename}: {diff}")
            continue

        prompt = (
            f"In ONE sentence (max 12 words), what does this Android code change do?\n"
            f"File: {filename}\n\n"
            f"{diff}\n\n"
            f"One sentence (start with a verb like adds, fixes, updates, removes):"
        )
        summary = call_gemma(prompt, model=model, max_tokens=35)
        summary = summary.splitlines()[0].strip().strip(".")
        summaries.append(f"- {filename}: {summary}")
        if verbose:
            print(f"    * {filename}: {summary}")

    if verbose:
        print(f"\n-> Pass 2: combining into one commit message...")

    combined = "\n".join(summaries)

    scope_line = ""
    if scope_hint:
        scope_line = (
            f"\nDetected feature scope: '{scope_hint}'.\n"
            f"Use this scope unless changes clearly span multiple features.\n"
        )

    final_prompt = (
        "You are an Android developer writing a git commit message.\n"
        "Here are summaries of every file changed in this commit:\n\n"
        f"{combined}\n"
        f"{scope_line}\n"
        "Write ONE commit message covering ALL of these changes together.\n"
        "Format:  <type>(<scope>): <description>\n"
        "Types:   feat, fix, refactor, chore, docs, test\n"
        "Rules:\n"
        "- Max 70 characters total\n"
        "- Present tense, lowercase description\n"
        "- MUST reflect ALL files above, not just one\n"
        "- Output ONLY the commit message, nothing else\n\n"
        "Commit message:"
    )

    message = call_gemma(final_prompt, model=model, max_tokens=80)
    return message.splitlines()[0].strip().strip('"').strip("'")


# -- Pipeline -----------------------------------------------------------------

def run(model=DEFAULT_MODEL, auto_commit=False, dry_run=False,
        use_scope=True, use_jira=True):

    print("-> Reading staged diff...")
    raw_diff = get_staged_diff()

    if not raw_diff.strip():
        print("  No staged changes. Run: git add <files>")
        sys.exit(0)

    file_map = split_by_file(raw_diff)
    print(f"  Found {len(file_map)} changed file(s)")

    kept, removed = filter_files(file_map)
    if removed:
        print(f"-> Filtered out {len(removed)} generated/junk file(s):")
        for path in removed:
            print(f"    x  {path}")

    if not kept:
        print("  No meaningful files remain after filtering.")
        sys.exit(0)

    ranked = rank_files(kept)
    print(f"-> Ranked {len(ranked)} file(s) by importance")

    tiered = tier_files(ranked)
    token_count = total_prompt_tokens(tiered)
    print(f"-> Tiered summary -- estimated tokens: ~{token_count}")

    for filepath, _, tier in tiered:
        icon = {"full": "*", "version": "~", "stats": "o"}.get(tier, "?")
        print(f"    {icon} [{tier:8}] {filepath}")

    if token_count > MAX_SAFE_TOKENS:
        print(f"\n  WARNING: Prompt size ({token_count}) > safe limit ({MAX_SAFE_TOKENS}).")
        print("     Consider using gemma3:12b for larger context.\n")

    scope_hint = None
    if use_scope:
        scope_hint = detect_scope(tiered)
        if scope_hint:
            print(f"-> Detected scope: '{scope_hint}'")
        else:
            print(f"-> No specific scope detected (will let model decide)")

    jira_ticket = None
    if use_jira:
        jira_ticket = detect_jira_ticket()
        if jira_ticket:
            print(f"-> Detected Jira ticket: {jira_ticket}")

    if dry_run:
        print("\n  [dry-run] Skipping Gemma call.")
        return

    print(f"\n-> Using model: {model}")
    message = generate_commit_message(tiered, model=model, scope_hint=scope_hint)

    if jira_ticket:
        message = prefix_message_with_ticket(message, jira_ticket)

    print(f"\n  +----------------------------------------------------------")
    print(f"  |  {message}")
    print(f"  +----------------------------------------------------------\n")

    if auto_commit:
        do_commit(message)
        return

    choice = input("  Use this message? [Y/n/e(dit)]: ").strip().lower()
    if choice in ("", "y"):
        do_commit(message)
    elif choice == "e":
        print("  (press Enter with no text to cancel)")
        edited = input("  Enter your message: ").strip()
        if edited:
            do_commit(edited)
        else:
            print("  Aborted -- no message entered.")
    else:
        print("  Aborted. No commit made.")


def do_commit(message):
    import subprocess
    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  Committed: {message}")
    else:
        print(f"  git commit failed:\n{result.stderr}")


# -- Git hook installer (works for both CLI and Android Studio) ---------------

def install_hook():
    """
    Install AutoCommit AI as a prepare-commit-msg hook.
    Works for:
      - Terminal:   git commit  (opens editor with AI message pre-filled)
      - GUI tools:  generates a .git/AUTOCOMMIT_MSG file the GUI can read

    For Android Studio, we ALSO write the message to a known file the user
    can copy from -- since AS doesn't honor prepare-commit-msg the way CLI does.
    """
    import subprocess

    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("[ERROR] Not inside a git repository.")
        sys.exit(1)

    git_dir = result.stdout.strip()
    hooks_dir = os.path.join(git_dir, "hooks")
    os.makedirs(hooks_dir, exist_ok=True)

    agent_path = os.path.abspath(__file__)
    python_exe = sys.executable    # absolute path -- works even when GUI shell has no PATH

    # ---- Hook 1: prepare-commit-msg (for terminal `git commit`) ----
    prepare_hook_path = os.path.join(hooks_dir, "prepare-commit-msg")
    prepare_hook = f"""#!/bin/sh
# AutoCommit AI -- prepare-commit-msg hook (terminal mode)
COMMIT_MSG_FILE="$1"
COMMIT_SOURCE="$2"

# Only run when no source is set (interactive editor commit)
if [ -n "$COMMIT_SOURCE" ]; then
    exit 0
fi

"{python_exe}" "{agent_path}" --auto-write "$COMMIT_MSG_FILE" 2>/dev/null || true
"""

    with open(prepare_hook_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(prepare_hook)
    try:
        os.chmod(prepare_hook_path, 0o755)
    except Exception:
        pass

    # ---- Hook 2: pre-commit (works with Android Studio + all GUIs) ----
    # This hook runs BEFORE the commit dialog appears in most GUIs and
    # writes the AI message to .git/AUTOCOMMIT_MSG for the user to copy.
    pre_commit_path = os.path.join(hooks_dir, "pre-commit")
    pre_commit = f"""#!/bin/sh
# AutoCommit AI -- pre-commit hook (GUI / Android Studio mode)
# Generates the message and writes it to .git/AUTOCOMMIT_MSG
# so it can be copied into Android Studio's commit dialog.

GIT_DIR=$(git rev-parse --git-dir)
"{python_exe}" "{agent_path}" --gui-write "$GIT_DIR/AUTOCOMMIT_MSG" 2>/dev/null || true
exit 0
"""

    with open(pre_commit_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(pre_commit)
    try:
        os.chmod(pre_commit_path, 0o755)
    except Exception:
        pass

    print(f"\n  Hooks installed in: {hooks_dir}")
    print(f"\n  TERMINAL  : 'git commit' opens editor with AI message pre-filled")
    print(f"  ANDROID STUDIO :")
    print(f"     1. Click 'Commit' in Android Studio (do NOT type a message yet)")
    print(f"     2. AutoCommit AI runs in background and writes the message to:")
    print(f"        {git_dir}/AUTOCOMMIT_MSG")
    print(f"     3. Run this command to copy the AI message to clipboard:")
    print(f"        type {git_dir}\\AUTOCOMMIT_MSG | clip")
    print(f"     4. Paste in Android Studio's commit message field")
    print(f"\n  TIP: For best Android Studio experience, use the manual command:")
    print(f"       python \"{agent_path}\" --auto")
    print(f"       This stages, generates, AND commits in one step.\n")


def uninstall_hook():
    import subprocess
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("[ERROR] Not inside a git repository.")
        sys.exit(1)

    git_dir = result.stdout.strip()
    hooks_dir = os.path.join(git_dir, "hooks")

    removed = []
    for hook_name in ["prepare-commit-msg", "pre-commit"]:
        path = os.path.join(hooks_dir, hook_name)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            if "AutoCommit AI" in content:
                os.remove(path)
                removed.append(hook_name)

    if removed:
        print(f"  Uninstalled hooks: {', '.join(removed)}")
    else:
        print("  No AutoCommit AI hooks found in this repo.")


def auto_write_to_file(commit_msg_file, model=DEFAULT_MODEL):
    """Hook mode: write to git's commit-msg file (terminal use)."""
    try:
        raw_diff = get_staged_diff()
        if not raw_diff.strip():
            return

        file_map = split_by_file(raw_diff)
        kept, _ = filter_files(file_map)
        if not kept:
            return

        ranked = rank_files(kept)
        tiered = tier_files(ranked)

        scope_hint = detect_scope(tiered)
        jira_ticket = detect_jira_ticket()

        message = generate_commit_message(tiered, model=model,
                                          scope_hint=scope_hint, verbose=False)
        if jira_ticket:
            message = prefix_message_with_ticket(message, jira_ticket)

        with open(commit_msg_file, "r", encoding="utf-8") as f:
            existing = f.read()

        with open(commit_msg_file, "w", encoding="utf-8") as f:
            f.write(message + "\n\n" + existing)

    except Exception as e:
        print(f"[AutoCommit AI] Skipped: {e}", file=sys.stderr)


def gui_write_to_file(target_file, model=DEFAULT_MODEL):
    """
    GUI mode: write the message to .git/AUTOCOMMIT_MSG so user can
    copy it into Android Studio / other GUI commit dialogs.
    Also copies it to clipboard automatically (Windows / macOS / Linux).
    """
    try:
        raw_diff = get_staged_diff()
        if not raw_diff.strip():
            return

        file_map = split_by_file(raw_diff)
        kept, _ = filter_files(file_map)
        if not kept:
            return

        ranked = rank_files(kept)
        tiered = tier_files(ranked)

        scope_hint = detect_scope(tiered)
        jira_ticket = detect_jira_ticket()

        message = generate_commit_message(tiered, model=model,
                                          scope_hint=scope_hint, verbose=False)
        if jira_ticket:
            message = prefix_message_with_ticket(message, jira_ticket)

        # Write to file
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(message)

        # Copy to clipboard for instant paste
        try:
            _copy_to_clipboard(message)
        except Exception:
            pass

    except Exception as e:
        print(f"[AutoCommit AI] Skipped: {e}", file=sys.stderr)


def _copy_to_clipboard(text):
    """Cross-platform clipboard copy without external deps."""
    import subprocess
    if sys.platform == "win32":
        subprocess.run(["clip"], input=text, text=True, check=False)
    elif sys.platform == "darwin":
        subprocess.run(["pbcopy"], input=text, text=True, check=False)
    else:
        # Linux -- try xclip then xsel
        if shutil.which("xclip"):
            subprocess.run(["xclip", "-selection", "clipboard"],
                           input=text, text=True, check=False)
        elif shutil.which("xsel"):
            subprocess.run(["xsel", "--clipboard", "--input"],
                           input=text, text=True, check=False)


# -- CLI ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="AutoCommit AI -- generate git commit messages with a local Gemma model."
    )
    parser.add_argument("--model", default=DEFAULT_MODEL,
        help=f"Ollama model (default: {DEFAULT_MODEL})")
    parser.add_argument("--auto", action="store_true",
        help="Commit automatically without confirmation")
    parser.add_argument("--dry-run", action="store_true",
        help="Preview pipeline output without calling Gemma")
    parser.add_argument("--no-scope", action="store_true",
        help="Disable scope auto-detection")
    parser.add_argument("--no-jira", action="store_true",
        help="Disable Jira ticket prefix")
    parser.add_argument("--install-hook", action="store_true",
        help="Install git hooks in the current repository")
    parser.add_argument("--uninstall-hook", action="store_true",
        help="Remove AutoCommit AI git hooks from current repo")
    parser.add_argument("--auto-write", metavar="COMMIT_MSG_FILE",
        help="(internal) Write message to commit msg file (terminal hook)")
    parser.add_argument("--gui-write", metavar="TARGET_FILE",
        help="(internal) Write message to file + clipboard (GUI hook)")

    args = parser.parse_args()

    if args.install_hook:
        install_hook()
        return
    if args.uninstall_hook:
        uninstall_hook()
        return
    if args.auto_write:
        auto_write_to_file(args.auto_write, model=args.model)
        return
    if args.gui_write:
        gui_write_to_file(args.gui_write, model=args.model)
        return

    run(
        model=args.model,
        auto_commit=args.auto,
        dry_run=args.dry_run,
        use_scope=not args.no_scope,
        use_jira=not args.no_jira,
    )


if __name__ == "__main__":
    main()