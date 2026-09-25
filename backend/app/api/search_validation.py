import re

from app.api.map_validation import MapRequestValidationError, parse_categories

MIN_SEARCH_QUERY_LENGTH = 2
MAX_SEARCH_QUERY_LENGTH = 100


def parse_search_query(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip().lower().replace("ё", "е"))
    if len(normalized) < MIN_SEARCH_QUERY_LENGTH:
        raise MapRequestValidationError(
            f"q must contain at least {MIN_SEARCH_QUERY_LENGTH} characters"
        )
    if len(normalized) > MAX_SEARCH_QUERY_LENGTH:
        raise MapRequestValidationError(
            f"q must contain no more than {MAX_SEARCH_QUERY_LENGTH} characters"
        )
    return normalized


def parse_optional_categories(value: str | None) -> tuple[str, ...]:
    return () if value is None else parse_categories(value)
