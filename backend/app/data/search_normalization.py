import unicodedata


def normalize_search_text(value: str) -> str:
    """Return the deterministic Search v2 comparison form without changing display text."""
    compatible = unicodedata.normalize("NFKC", value).replace("\u00a0", " ")
    return " ".join(compatible.lower().replace("ё", "е").split())
