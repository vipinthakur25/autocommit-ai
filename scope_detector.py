"""
Smart scope detection for Android projects.

Tries to infer the most specific scope (e.g. 'auth', 'home', 'profile')
from the changed files using two strategies:

  1. Folder-path strategy  → e.g. app/src/main/java/com/x/auth/Login.kt → 'auth'
  2. Package-name strategy → reads `package` declaration in the file → 'auth'

The most frequent specific scope across all changed files wins.
Falls back to 'core' if nothing meaningful is detected.
"""

import re
from collections import Counter

# Folders that don't represent a feature scope — skip them when scanning paths.
GENERIC_FOLDERS = {
    "java", "kotlin", "main", "src", "app", "com",
    "ui", "data", "domain", "presentation", "core",
    "android", "androidx", "google", "model", "models",
    "util", "utils", "common", "base", "ext", "extensions",
    "theme", "components", "widget", "widgets",
    "viewmodel", "viewmodels", "repository", "repositories",
    "network", "api", "di", "module", "modules",
    "test", "androidtest", "res", "assets",
}

PACKAGE_REGEX = re.compile(r"^\s*package\s+([\w\.]+)", re.MULTILINE)


def _scope_from_path(filepath):
    """
    Walk the path segments and return the deepest non-generic folder name.
    Example:  app/src/main/java/com/vipin/bubbletranslate/auth/Login.kt → 'auth'
    """
    parts = filepath.replace("\\", "/").split("/")
    # Drop the file name itself
    parts = parts[:-1]

    # Walk from deepest folder upward — first non-generic name wins
    for segment in reversed(parts):
        seg_lower = segment.lower()
        if seg_lower not in GENERIC_FOLDERS and not seg_lower.isdigit():
            # Skip very long segments (likely package roots like 'bubbletranslate')
            if 2 <= len(seg_lower) <= 15:
                return seg_lower
    return None


def _scope_from_package(diff_content):
    """
    Extract `package com.x.y.scope` declaration from the diff content
    and return the last non-generic segment.
    """
    match = PACKAGE_REGEX.search(diff_content)
    if not match:
        return None

    parts = match.group(1).split(".")
    # Walk from deepest segment backwards
    for segment in reversed(parts):
        if segment.lower() not in GENERIC_FOLDERS and len(segment) >= 2:
            # Skip the project's own root package (heuristic: 8+ chars often = app name)
            if 2 <= len(segment) <= 15:
                return segment.lower()
    return None


def detect_scope(tiered_files):
    """
    Run smart detection across all changed files and return the
    most common specific scope.

    tiered_files: list of (filepath, diff, tier) tuples
    Returns: a string scope (e.g. 'auth') or None if nothing detected.
    """
    scope_votes = Counter()

    for filepath, diff, _tier in tiered_files:
        # Strategy 1: folder path
        path_scope = _scope_from_path(filepath)
        if path_scope:
            scope_votes[path_scope] += 1

        # Strategy 2: package declaration (only if diff has content)
        if diff and len(diff) > 50:
            pkg_scope = _scope_from_package(diff)
            if pkg_scope:
                # Package match is slightly more reliable — give it weight 2
                scope_votes[pkg_scope] += 2

    if not scope_votes:
        return None

    # Return the most-voted scope
    most_common, _count = scope_votes.most_common(1)[0]
    return most_common