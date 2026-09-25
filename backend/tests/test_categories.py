# ruff: noqa: E501
import json
from pathlib import Path

import pytest

from app.data.categories import Condition, Rule, load_category_config, match_rule


def test_config_and_deterministic_rule_matching() -> None:
    categories, rules = load_category_config()
    assert len(categories) == 10
    assert [rule.id for rule in rules] == sorted(rule.id for rule in rules)
    road = next(rule for rule in rules if rule.id == "osm.road.highway")
    assert match_rule(road, {"highway": "primary"}, "way", "line", "feature") == {
        "highway": "primary"
    }
    assert match_rule(road, {"highway": "primary"}, "node", "point", "feature") is None
    river = next(rule for rule in rules if rule.id == "osm.water.riverway")
    assert match_rule(river, {"waterway": "river"}, "way", "line", "feature") == {
        "waterway": "river"
    }
    assert match_rule(river, {"waterway": "stream"}, "way", "line", "feature") is None
    assert match_rule(river, {"waterway": "river"}, "relation", "line", "feature") is None


@pytest.mark.parametrize(
    ("operator", "value", "tags", "expected"),
    [
        ("equals", "school", {"amenity": "school"}, True),
        ("in", ("school", "college"), {"amenity": "college"}, True),
        ("exists", None, {"amenity": "cafe"}, True),
        ("not_equals", "cafe", {"amenity": "school"}, True),
        ("not_in", ("cafe", "bar"), {"amenity": "school"}, True),
    ],
)
def test_supported_operators(
    operator: str, value: object, tags: dict[str, str], expected: bool
) -> None:
    rule = Rule("test", "1", "test", (Condition("amenity", operator, value),))  # type: ignore[arg-type]
    assert (match_rule(rule, tags, "node", "point", "feature") is not None) is expected


def test_rejects_duplicate_unknown_and_unsupported_rules(tmp_path: Path) -> None:
    base = tmp_path / "config/categories/sources"
    base.mkdir(parents=True)
    (tmp_path / "config/categories/taxonomy.json").write_text(
        json.dumps({"categories": [{"key": "known", "label": "Known"}]}), encoding="utf-8"
    )
    source = base / "osm.json"
    source.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "x",
                        "version": "1",
                        "category": "unknown",
                        "conditions": [{"tag": "a", "operator": "exists"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unknown category"):
        load_category_config(tmp_path)
    source.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "x",
                        "version": "1",
                        "category": "known",
                        "conditions": [{"tag": "a", "operator": "eval"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unsupported operator"):
        load_category_config(tmp_path)
    duplicate = {
        "id": "x",
        "version": "1",
        "category": "known",
        "conditions": [{"tag": "a", "operator": "exists"}],
    }
    source.write_text(json.dumps({"rules": [duplicate, duplicate]}), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate rule"):
        load_category_config(tmp_path)
