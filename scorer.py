def score_file(filepath):
    """
    Score a file by how much semantic value it adds to a commit message.
    Higher = more important = gets more token budget.
    """
    score = 0

    # --- Language bonuses ---
    if filepath.endswith(".kt"):
        score += 10
    if filepath.endswith(".java"):
        score += 8

    # --- Android architecture layer bonuses ---
    high_value_keywords = [
        "ViewModel", "Repository", "UseCase",
        "Interactor", "Service", "Manager",
        "Datasource", "DataSource", "ApiService",
        "Dao", "Database", "Worker",
    ]
    for kw in high_value_keywords:
        if kw in filepath:
            score += 6

    # --- UI layer bonuses ---
    ui_keywords = ["Activity", "Fragment", "Adapter",
                   "Composable", "Screen", "Component"]
    for kw in ui_keywords:
        if kw in filepath:
            score += 4

    # --- Model / data layer ---
    model_keywords = ["Model", "Entity", "Dto",
                      "Response", "Request", "Mapper"]
    for kw in model_keywords:
        if kw in filepath:
            score += 3

    # --- Low value file types ---
    if filepath.endswith(".xml"):
        score -= 3          # verbose but rarely the star of a commit message
    if filepath.endswith(".json"):
        score -= 2
    if filepath.endswith(".md"):
        score -= 4

    # --- Test files: relevant but lower priority ---
    if "test" in filepath.lower() or "Test" in filepath:
        score -= 2

    # --- Gradle: handled by version-only tier, deprioritise here ---
    if filepath.endswith(".gradle") or filepath.endswith(".kts"):
        score -= 1

    return score


def rank_files(file_map):
    """
    Return a list of (filepath, diff) tuples sorted by importance (desc).
    """
    return sorted(
        file_map.items(),
        key=lambda x: score_file(x[0]),
        reverse=True
    )
