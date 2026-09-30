from uuid import UUID

from app.data.facilities import (
    CANDIDATE_SQL,
    CandidateObject,
    CandidatePair,
    _build_groups,
    _evidence,
    _geometry_role,
)


def candidate_object(
    value: int,
    *,
    geometry_type: str,
    geometry_role: str,
    tags: dict[str, str],
) -> CandidateObject:
    return CandidateObject(
        id=UUID(int=value),
        source_id=1,
        source_type="node" if geometry_type == "POINT" else "way",
        source_object_id=str(value),
        name=tags.get("name"),
        geometry_type=geometry_type,
        geometry_role=geometry_role,
        tags=tags,
    )


def pair(
    point: CandidateObject,
    area: CandidateObject,
    *,
    category: str = "healthcare.clinic",
    methods: tuple[str, ...] = ("exact_ref",),
) -> CandidatePair:
    return CandidatePair(
        category_key=category,
        point=point,
        area=area,
        contained=True,
        distance_meters=0,
        shared_site_relations=(),
        strong=True,
        methods=methods,
        rejected_reason=None,
    )


def test_link_evidence_rejects_proximity_generic_building_and_contradictory_ref() -> None:
    assert _evidence(
        "healthcare.clinic",
        {"amenity": "clinic", "name": "First"},
        {"amenity": "clinic", "building": "yes", "name": "Second"},
        "BUILDING",
        contained=True,
        shared_site_relations=(),
    ) == (False, (), None)
    assert _evidence(
        "education.school",
        {"amenity": "school"},
        {"building": "yes"},
        "BUILDING",
        contained=True,
        shared_site_relations=(),
    ) == (False, (), None)
    assert _evidence(
        "education.school",
        {"amenity": "school", "ref": "12"},
        {"amenity": "school", "ref": "13"},
        "FACILITY_SITE",
        contained=True,
        shared_site_relations=(),
    ) == (False, (), "contradictory_ref")
    assert _evidence(
        "healthcare.clinic",
        {
            "amenity": "clinic",
            "name": "Поликлиника №104",
            "addr:street": "улица Сикейроса",
            "addr:housenumber": "10",
        },
        {
            "amenity": "clinic",
            "name": "Диагностический центр №1",
            "addr:street": "улица Сикейроса",
            "addr:housenumber": "10",
        },
        "FACILITY_SITE",
        contained=True,
        shared_site_relations=(),
    ) == (False, (), None)


def test_exact_ref_and_explicit_site_membership_are_strong() -> None:
    exact_ref = _evidence(
        "education.kindergarten",
        {"amenity": "kindergarten", "ref": "115"},
        {"amenity": "kindergarten", "ref": "115"},
        "FACILITY_SITE",
        contained=False,
        shared_site_relations=(),
    )
    assert exact_ref == (True, ("exact_ref",), None)

    explicit = _evidence(
        "healthcare.hospital",
        {"amenity": "hospital"},
        {"amenity": "hospital"},
        "FACILITY_SITE",
        contained=False,
        shared_site_relations=(42,),
    )
    assert explicit == (True, ("explicit_site_relation",), None)


def test_geometry_roles_keep_buildings_distinct_from_sites() -> None:
    assert _geometry_role(
        "education.kindergarten", "POLYGON", {"amenity": "kindergarten"}
    ) == "FACILITY_SITE"
    assert _geometry_role(
        "education.kindergarten",
        "POLYGON",
        {"amenity": "kindergarten", "building": "kindergarten"},
    ) == "BUILDING"
    assert _geometry_role("education.school", "POLYGON", {"landuse": "education"}) == "OTHER_AREA"
    assert _geometry_role("healthcare.clinic", "POINT", {"amenity": "clinic"}) == "POINT"


def test_ambiguous_point_to_two_sites_is_not_grouped() -> None:
    point = candidate_object(
        1,
        geometry_type="POINT",
        geometry_role="POINT",
        tags={"amenity": "school", "ref": "10"},
    )
    first = candidate_object(
        2,
        geometry_type="POLYGON",
        geometry_role="FACILITY_SITE",
        tags={"amenity": "school", "ref": "10"},
    )
    second = candidate_object(
        3,
        geometry_type="POLYGON",
        geometry_role="FACILITY_SITE",
        tags={"amenity": "school", "ref": "10"},
    )

    groups, conflicts = _build_groups(
        [
            pair(point, first, category="education.school"),
            pair(point, second, category="education.school"),
        ]
    )

    assert groups == []
    assert conflicts == 1


def test_site_building_and_point_group_has_role_specific_geometry() -> None:
    point = candidate_object(
        10,
        geometry_type="POINT",
        geometry_role="POINT",
        tags={"amenity": "clinic", "name": "Clinic", "ref": "A"},
    )
    site = candidate_object(
        11,
        geometry_type="POLYGON",
        geometry_role="FACILITY_SITE",
        tags={"amenity": "clinic", "name": "Clinic", "ref": "A"},
    )
    building = candidate_object(
        12,
        geometry_type="POLYGON",
        geometry_role="BUILDING",
        tags={"amenity": "clinic", "building": "yes", "ref": "A"},
    )

    groups, conflicts = _build_groups([pair(point, site), pair(point, building)])

    assert conflicts == 0
    assert len(groups) == 1
    assert len(groups[0].members) == 3
    assert groups[0].display_object_id == site.id
    assert groups[0].analysis_object_id == site.id


def test_candidate_query_is_same_category_and_spatially_bounded() -> None:
    sql = str(CANDIDATE_SQL)
    assert "area.category_key=point.category_key" in sql
    assert "ST_DWithin" in sql
    assert "ST_Expand" in sql
    assert "type'='site" in sql
