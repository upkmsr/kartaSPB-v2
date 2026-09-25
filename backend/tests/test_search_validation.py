import pytest

from app.api.map_validation import MapRequestValidationError
from app.api.search_validation import parse_optional_categories, parse_search_query


def test_search_query_normalizes_case_whitespace_and_yo() -> None:
    assert parse_search_query("  ЁЛОЧНАЯ   Аптека ") == "елочная аптека"


@pytest.mark.parametrize("value", ["", " ", "a", "я", "не", "x" * 101])
def test_search_query_rejects_invalid_lengths(value: str) -> None:
    with pytest.raises(MapRequestValidationError):
        parse_search_query(value)


def test_search_query_accepts_three_characters() -> None:
    assert parse_search_query("нев") == "нев"


def test_optional_categories_uses_existing_category_contract() -> None:
    assert parse_optional_categories(None) == ()
    assert parse_optional_categories("nature.park,nature.park") == ("nature.park",)
