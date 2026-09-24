import math

import pytest

from app.api.map_validation import MapRequestValidationError, parse_bbox, parse_categories


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
