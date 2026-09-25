import math

import pytest

from app.api.map_validation import (
    MapRequestValidationError,
    parse_bbox,
    parse_categories,
    parse_districts,
)


def test_bbox_parser() -> None:
    bbox = parse_bbox("30.30,59.93,30.32,59.945")

    assert bbox.min_lon == 30.30
    assert bbox.min_lat == 59.93
    assert bbox.max_lon == 30.32
    assert bbox.max_lat == 59.945


@pytest.mark.parametrize(
    "value",
    [
        "30,59,31",
        "west,59,31,60",
        f"30,59,{math.inf},60",
        "-181,59,30,60",
        "30,-91,31,60",
        "31,59,30,60",
        "30,60,31,59",
    ],
)
def test_bbox_rejects_invalid_coordinates(value: str) -> None:
    with pytest.raises(MapRequestValidationError):
        parse_bbox(value)


def test_bbox_rejects_excessive_spans_and_area() -> None:
    with pytest.raises(MapRequestValidationError, match="longitude span"):
        parse_bbox("30,59,30.5001,59.1")
    with pytest.raises(MapRequestValidationError, match="latitude span"):
        parse_bbox("30,59,30.1,59.3001")
    with pytest.raises(MapRequestValidationError, match="area"):
        parse_bbox("30,59,30.5,59.25")


def test_category_parser_deduplicates_and_preserves_order() -> None:
    assert parse_categories("nature.park, education.school,nature.park") == (
        "nature.park",
        "education.school",
    )


def test_category_parser_rejects_empty_and_more_than_ten() -> None:
    with pytest.raises(MapRequestValidationError):
        parse_categories("")
    with pytest.raises(MapRequestValidationError):
        parse_categories("a,,b")
    with pytest.raises(MapRequestValidationError):
        parse_categories(",".join(f"category-{index}" for index in range(11)))


def test_district_parser_deduplicates_and_preserves_order() -> None:
    first = "01992d00-0fe0-54cd-99db-b35bbb7f34e2"
    second = "5d5648bf-d176-55ba-a665-fe4b2677396c"

    parsed = parse_districts(f"{first},{second},{first}")

    assert tuple(str(item) for item in parsed) == (first, second)
    assert parse_districts(None) == ()


def test_district_parser_rejects_invalid_empty_and_more_than_eighteen() -> None:
    with pytest.raises(MapRequestValidationError, match="valid UUIDs"):
        parse_districts("not-a-uuid")
    with pytest.raises(MapRequestValidationError, match="empty IDs"):
        parse_districts("")
    with pytest.raises(MapRequestValidationError, match="18"):
        parse_districts(
            ",".join(f"00000000-0000-0000-0000-{index:012d}" for index in range(1, 20))
        )
