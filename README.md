# AutoCommit AI

A local AI agent that generates conventional git commit messages for Android projects, powered by Gemma running entirely on your machine. No cloud calls, no API keys, no token costs.

Built specifically to handle the unique challenges of Android diffs — large file counts, generated code noise, and verbose XML resources — while staying within a small local model's context window.

---

## Why This Exists

A typical Android commit involves 10–20 files spanning Kotlin, XML layouts, Gradle configs, and auto-generated Java. A raw `git diff` on these changes can easily exceed 12,000 tokens, which overflows the context window of small local models like Gemma 1B (8,192 tokens).

AutoCommit AI solves this by passing the diff through a multi-stage pipeline that aggressively reduces token count without losing semantic meaning, then uses a two-pass approach to generate commit messages that reflect every changed file — not just the most "interesting" one.

---

## Features

- **Fully local execution** — runs on Ollama with Gemma 3 (1B, 4B, or 12B). No data leaves your machine.
- **Smart diff filtering** — automatically excludes generated files (`R.java`, `BuildConfig`, databinding classes, build artifacts) before they consume context.
- **Tiered summarization** — high-value Kotlin and Java files get full diffs; Gradle files get version-line extracts; XML resources get stat summaries only.
- **Two-pass generation** — Pass 1 summarizes each file individually, Pass 2 combines summaries into one cohesive commit message. Forces multi-file awareness even on smaller models.
- **Smart scope detection** — infers commit scope from folder paths and Kotlin package declarations, voting across all changed files.
- **Jira ticket prefixing** — extracts ticket IDs (`PROJ-123`, `AUTH-99`) from your branch name and inserts them into the commit message.
- **Git hook integration** — installs as a `prepare-commit-msg` hook to run automatically on every `git commit`.
- **Conventional Commits format** — outputs `feat(scope): description` style messages out of the box.

---

## Installation

### Prerequisites

- Python 3.8 or higher
- Git
- Ollama installed and running

### Step 1 — Install Ollama and pull Gemma

Download Ollama from [ollama.com](https://ollama.com/download), then pull a Gemma model:

```bash
ollama pull gemma3:1b      # fastest, ~1.5 GB RAM
ollama pull gemma3:4b      # better quality, ~5 GB RAM (recommended)
ollama pull gemma3:12b     # best quality, ~12 GB RAM
```

### Step 2 — Clone this repository

```bash
git clone https://github.com/vipinthakur25/autocommit-ai.git
cd autocommit-ai
```

### Step 3 — Install Python dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Verify the setup

```bash
python main.py --dry-run
```

If you see the pipeline output without errors, you're good to go.

---

## Usage

### Manual mode

Stage your changes, then run AutoCommit AI from inside any git repository:

```bash
git add .
python /path/to/autocommit-ai/main.py
```

The agent will:
1. Read your staged diff
2. Filter out generated files
3. Score and rank remaining files
4. Build a token-optimized prompt
5. Generate a commit message via Gemma
6. Show the suggestion and ask for confirmation

### Git hook mode

Install AutoCommit AI as a git hook in any repository:

```bash
cd /your/project
python /path/to/autocommit-ai/main.py --install-hook
```

After installation, every `git commit` (without `-m`) will open your editor with the AI-generated message pre-filled. You can edit, accept, or reject it as usual.

To uninstall the hook, simply delete `.git/hooks/prepare-commit-msg`.

### Command-line options

| Flag | Description |
|------|-------------|
| `--model gemma3:4b` | Use a specific Ollama model (default: `gemma3:1b`) |
| `--auto` | Skip confirmation, commit immediately |
| `--dry-run` | Show pipeline output without calling the model |
| `--no-scope` | Disable scope auto-detection |
| `--no-jira` | Disable Jira ticket prefix |
| `--install-hook` | Install as a git hook in the current repo |

---

## How the Pipeline Works

```
git diff --staged
        |
        v
[1] Filter Stage          remove R.java, BuildConfig, generated/, build/, .idea/
        |
        v
[2] Importance Scorer     rank files: Kotlin > Java > XML, ViewModels boosted
        |
        v
[3] Tiered Summarizer     Tier 1: full diff (top Kotlin files within budget)
                          Tier 2: version-only lines (Gradle)
                          Tier 3: stats only ("42 additions, 3 deletions")
        |
        v
[4] Scope Detector        vote-based scope inference from folder + package
        |
        v
[5] Two-Pass Generator    Pass 1: per-file one-line summaries
                          Pass 2: combine into single commit message
        |
        v
[6] Jira Prefixer         insert ticket ID from current branch name
        |
        v
   Commit message
```

A 15-file Android diff that would normally consume ~12,000 tokens is reduced to roughly 1,800 tokens before the model ever sees it.

---

## Example Output

For a commit touching `Data.kt` and `TranslationViewModel.kt`:

```
-> Reading staged diff...
   Found 2 changed file(s)
-> Ranked 2 file(s) by importance
-> Tiered summary -- estimated tokens: ~329
   * [full] app/src/main/java/com/app/translate/Data.kt
   * [full] app/src/main/java/com/app/translate/TranslationViewModel.kt
-> Detected scope: 'translate'
-> Detected Jira ticket: PROJ-123

-> Pass 1: reading each file...
   * Data.kt: adds DataUser data class with name and age fields
   * TranslationViewModel.kt: adds StateFlow for translation UI state

-> Pass 2: combining into one commit message...

  +----------------------------------------------------------
  |  feat(translate): [PROJ-123] add user data and state flow
  +----------------------------------------------------------

  Use this message? [Y/n/e(dit)]:
```

---

## Project Structure

```
autocommit-ai/
├── main.py              entry point and pipeline orchestrator
├── diff_extractor.py    reads git staged diff and splits per-file
├── filter.py            removes generated and irrelevant files
├── scorer.py            ranks files by semantic importance
├── summarizer.py        applies 3-tier token reduction
├── prompt_builder.py    assembles the final prompt for Gemma
├── scope_detector.py    infers commit scope from paths and packages
├── jira_detector.py     extracts Jira tickets from branch names
├── requirements.txt     Python dependencies
├── LICENSE              MIT license
└── README.md
```

---

## Performance

Tested on a typical Android feature commit (8 Kotlin files, 3 XML layouts, 1 Gradle file, 2 generated):

| Stage | Tokens |
|-------|--------|
| Raw diff | 11,420 |
| After filter | 6,180 |
| After scoring | 6,180 |
| After tiering | 2,240 |
| Final prompt (Pass 2) | 380 |

End-to-end time on Gemma 3:1B: approximately 4–7 seconds.
End-to-end time on Gemma 3:4B: approximately 12–20 seconds.

---

## Configuration

Most behavior can be tuned by editing constants at the top of each module:

- `MAX_PROMPT_TOKENS` and `FULL_DIFF_BUDGET` in `summarizer.py`
- `EXCLUDE_PATTERNS` in `filter.py` to add or remove file exclusions
- `GENERIC_FOLDERS` in `scope_detector.py` to refine scope detection
- `DEFAULT_MODEL` in `main.py` to change the default Ollama model

---

## Limitations

- Gemma 1B may produce generic messages on commits spanning many unrelated files. Use Gemma 4B for better synthesis quality.
- Scope detection works best on projects following standard Android package conventions (`com.company.app.feature`).
- The agent does not currently parse `.proto`, `.cpp`, or NDK files specially — they're treated as generic source files.
- Currently optimized for English commit messages.

---

## Roadmap

- Multi-language commit message support
- Configurable commit message templates
- Integration with Conventional Commits scope conventions per team
- Web-based configuration UI
- Pre-commit linting integration

---

## Contributing

Contributions are welcome. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on submitting issues, feature requests, and pull requests.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Acknowledgments

Built with [Ollama](https://ollama.com) and [Google Gemma](https://ai.google.dev/gemma). Inspired by the daily friction of writing meaningful commit messages on large Android codebases.
