# Contributing to AutoCommit AI

Thank you for your interest in contributing. This document outlines how to report issues, propose features, and submit pull requests.

## Reporting Issues

Before opening an issue, please search existing issues to avoid duplicates. When filing a new issue, include:

- A clear, descriptive title
- Steps to reproduce the problem
- Expected behavior versus actual behavior
- Your operating system, Python version, and Ollama model used
- Sample diff or commit context if relevant (with sensitive data redacted)

## Proposing Features

Feature requests are welcome. Please open an issue with the `enhancement` label and describe:

- The problem you're trying to solve
- Why existing functionality doesn't address it
- A rough proposal for how the feature might work
- Any relevant prior art from similar tools

## Submitting Pull Requests

### Setup

Fork the repository and clone your fork locally:

```bash
git clone https://github.com/YOUR_USERNAME/autocommit-ai.git
cd autocommit-ai
pip install -r requirements.txt
```

### Branch Naming

Use descriptive branch names following this pattern:

- `feature/description-of-feature`
- `fix/description-of-bug`
- `docs/description-of-doc-change`

### Code Style

- Follow PEP 8 for Python code
- Keep functions focused and under 40 lines where reasonable
- Add docstrings for any new public functions
- Prefer clarity over cleverness

### Testing Your Changes

Before submitting a PR, verify that:

1. `python main.py --dry-run` works in any git repository
2. `python main.py --install-hook` correctly installs the git hook
3. The pipeline handles edge cases (empty diff, only generated files, etc.)
4. Token reduction stays under `MAX_SAFE_TOKENS` for typical Android diffs

### Pull Request Checklist

- [ ] Code follows the existing style
- [ ] New functions have docstrings
- [ ] README is updated if behavior or usage changed
- [ ] Commit messages follow Conventional Commits (use AutoCommit AI itself)
- [ ] Changes are tested on at least one real Android repository

## Areas Where Help Is Welcome

- Additional language support (non-English commit messages)
- Support for non-Android project types (iOS, web, backend)
- Better tier-3 summarization (currently just stats)
- Configuration file support (so users don't have to edit constants)
- Test suite

## Code of Conduct

Be respectful, constructive, and patient. This is a community project — assume good faith from contributors and reviewers alike.

## License

By contributing, you agree that your contributions will be licensed under the MIT License that covers the project.
