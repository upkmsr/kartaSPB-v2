from uuid import UUID

from app.data.search_normalization import normalize_search_text
from app.data.streets import StreetCandidate, _build_groups, _display_text


def candidate(
    value: int,
    name: str,
    component: int,
    *relations: str,
) -> StreetCandidate:
    return StreetCandidate(
        id=UUID(int=value),
        name=name,
        search_name=normalize_search_text(name),
        spatial_component=component,
        source_type="way",
        source_object_id=str(value),
        tags={"highway": "residential", "name": name},
        relation_keys=relations,
    )


def test_search_normalization_handles_nfkc_nbsp_whitespace_and_yo() -> None:
    assert normalize_search_text("  Ａ\u00a0  Ёлочная  ") == "a елочная"


def test_display_text_preserves_human_compatibility_characters() -> None:
    assert _display_text("  Дорога №\u00a07  ") == "Дорога №\u00a07"


def test_groups_spatial_components_without_global_same_name_merge() -> None:
    groups = _build_groups(
        [
            candidate(1, "Центральная улица", 0),
            candidate(2, "Центральная улица", 0),
            candidate(3, "Центральная улица", 1),
            candidate(4, "Другая улица", 0),
        ]
    )
    central = [group for group in groups if group.search_name == "центральная улица"]
    assert sorted(len(group.members) for group in central) == [1, 2]
    assert len([group for group in groups if group.search_name == "другая улица"]) == 1


def test_explicit_relation_can_join_same_name_spatial_components() -> None:
    relation = "1:street:100"
    groups = _build_groups(
        [
            candidate(1, "Невский проспект", 0, relation),
            candidate(2, "Невский проспект", 1, relation),
        ]
    )
    assert len(groups) == 1
    assert len(groups[0].members) == 2
    assert groups[0].link_method.endswith("+explicit_osm_relation")
