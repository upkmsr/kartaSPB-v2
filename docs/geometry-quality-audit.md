# F5.5-S4 geometry quality audit

Date: 2026-09-29

Production snapshot: full `spb_city` refresh from the registered
`northwestern-fed-district-20260921T231045Z.osm.pbf` source

Scope: the ten enabled baseline categories and the authoritative union of the 18
Saint Petersburg districts

## Result

The canonical geometries are structurally healthy: there are no null, empty, invalid,
wrong-SRID, or unsupported geometries in any baseline category. The user-visible point
representation of some facilities is not a general geometry assembly failure. It is
mostly the consequence of distinct OSM source identities being preserved as distinct
canonical objects while the product has no logical facility or role-aware display
geometry layer.

The evidence supports a separate **F5.5-S4R — Logical Facility Entity / Representation
Group** phase. It must preserve every source identity and add conservative,
category-specific links plus explicit source, display, and analysis geometry roles. It
must not automatically treat a containing generic building or a nearby area as the same
facility. No remediation is implemented by this audit.

Audit snapshot: Alembic `20260928_0008`, 417,331 active canonical objects,
417,332 active category assignments, and 18 enabled district bindings.

## Method and safety

All production queries were read-only and category-scoped. Candidate searches used a
geometry bbox prefilter, a 100 m maximum geography distance, and at most 8 MiB query
`work_mem`. No production table, migration, category rule, API, search behavior, map
style, or canonical object was changed.

Two populations are reported deliberately:

- **global active** is the complete imported canonical population and therefore includes
  reference-complete source objects outside the city;
- **SPb** intersects the unary union of the 18 enabled authoritative district geometries
  and is the primary population for facility conclusions.

The 3–16,794 outside-city objects per category are expected reference-closure/import
coverage, not deletion candidates.

## Geometry distribution

The first table is global active production data. Each cell is `count (percentage of
category)`; `other` includes GeometryCollection and any type not named in the table.

| Category | Total | Point | LineString | MultiLineString | Polygon | MultiPolygon | Other |
|---|---:|---:|---:|---:|---:|---:|---:|
| `boundary.administrative` | 791 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 758 (95.8%) | 33 (4.2%) | 0 |
| `education.kindergarten` | 1,650 | 345 (20.9%) | 0 | 0 | 1,296 (78.5%) | 9 (0.5%) | 0 |
| `education.school` | 1,077 | 93 (8.6%) | 0 | 0 | 976 (90.6%) | 8 (0.7%) | 0 |
| `healthcare.clinic` | 695 | 524 (75.4%) | 0 | 0 | 171 (24.6%) | 0 | 0 |
| `healthcare.hospital` | 173 | 14 (8.1%) | 0 | 0 | 157 (90.8%) | 2 (1.2%) | 0 |
| `healthcare.pharmacy` | 2,546 | 2,513 (98.7%) | 0 | 0 | 33 (1.3%) | 0 | 0 |
| `nature.park` | 1,582 | 0 | 0 | 0 | 1,471 (93.0%) | 111 (7.0%) | 0 |
| `nature.water` | 4,332 | 0 | 1,441 (33.3%) | 0 | 2,860 (66.0%) | 31 (0.7%) | 0 |
| `transport.road` | 385,886 | 0 | 385,886 (100.0%) | 0 | 0 | 0 | 0 |
| `transport.stop` | 18,600 | 18,600 (100.0%) | 0 | 0 | 0 | 0 | 0 |

The authoritative SPb population is:

| Category | Total | Point | LineString | Polygon | MultiPolygon | Global outside SPb |
|---|---:|---:|---:|---:|---:|---:|
| `boundary.administrative` | 160 | 0 | 0 | 149 | 11 | 631 |
| `education.kindergarten` | 1,574 | 326 | 0 | 1,239 | 9 | 76 |
| `education.school` | 1,061 | 92 | 0 | 961 | 8 | 16 |
| `healthcare.clinic` | 677 | 510 | 0 | 167 | 0 | 18 |
| `healthcare.hospital` | 170 | 14 | 0 | 154 | 2 | 3 |
| `healthcare.pharmacy` | 2,404 | 2,371 | 0 | 33 | 0 | 142 |
| `nature.park` | 1,573 | 0 | 0 | 1,462 | 111 | 9 |
| `nature.water` | 3,398 | 0 | 574 | 2,793 | 31 | 934 |
| `transport.road` | 369,092 | 0 | 369,092 | 0 | 0 | 16,794 |
| `transport.stop` | 12,741 | 12,741 | 0 | 0 | 0 | 5,859 |

## Validity

Across all ten global active category populations:

| Check | Count |
|---|---:|
| NULL geometry | 0 |
| Empty geometry | 0 |
| Invalid geometry | 0 |
| SRID other than 4326 | 0 |
| GeometryCollection | 0 |
| Unsupported/other type | 0 |

The authoritative 18 district bindings remain present and stable. Boundary objects are
valid Polygon/MultiPolygon relation products; the generic administrative category is
broader than the domain district registry and must not replace it.

## Source identity by geometry

| Category | OSM source type | Canonical geometry | Count |
|---|---|---|---:|
| boundary.administrative | relation | Polygon / MultiPolygon | 758 / 33 |
| education.kindergarten | node | Point | 345 |
|  | way | Polygon | 1,036 |
|  | relation | Polygon / MultiPolygon | 260 / 9 |
| education.school | node | Point | 93 |
|  | way | Polygon | 736 |
|  | relation | Polygon / MultiPolygon | 240 / 8 |
| healthcare.clinic | node | Point | 524 |
|  | way | Polygon | 148 |
|  | relation | Polygon | 23 |
| healthcare.hospital | node | Point | 14 |
|  | way | Polygon | 89 |
|  | relation | Polygon / MultiPolygon | 68 / 2 |
| healthcare.pharmacy | node | Point | 2,513 |
|  | way | Polygon | 30 |
|  | relation | Polygon | 3 |
| nature.park | way | Polygon | 1,146 |
|  | relation | Polygon / MultiPolygon | 325 / 111 |
| nature.water | way | LineString / Polygon | 1,441 / 2,328 |
|  | relation | Polygon / MultiPolygon | 532 / 31 |
| transport.road | way | LineString | 385,886 |
| transport.stop | node | Point | 18,600 |

This is internally consistent: the canonical geometry follows the selected source OSM
identity. A node and a way with different OSM IDs remain different provenance records.

## Building versus facility site

Area objects carrying a facility category and `building=*` were classified as
**BUILDING**. Categorized areas without `building=*` were classified as
**FACILITY_SITE** (or park area for parks). A generic containing footprint is not a
facility site and is not entity evidence on its own.

| Category | Area total | Building-tagged | Building + category semantics | Non-building category area |
|---|---:|---:|---:|---:|
| kindergarten | 1,305 | 18 | 18 | 1,287 |
| school | 984 | 55 | 55 | 929 |
| clinic | 171 | 122 | 122 | 49 |
| hospital | 159 | 23 | 23 | 136 |
| pharmacy | 33 | 6 | 6 | 27 |
| park | 1,582 | 0 | 0 | 1,582 |

For global point objects, containment in a building footprint was common but usually did
not establish identity: kindergarten 339/345, school 93/93, clinic 520/524, hospital
14/14, and pharmacy 2,495/2,513. Of the kindergarten points, only 11 were in a
`building=kindergarten` footprint; 328 were in generic/other buildings and 6 were in no
building. Therefore “point is inside a building” is not an acceptable merge rule.

## Candidate methodology

A point/area pair enters the diagnostic candidate set only when it has the same category
and is contained or within 100 m. Identity evidence is an exact normalized non-empty
name, operator, ref, or full street-plus-house-number match; non-breaking spaces are
normalized. Name is supporting evidence, never an independent merge key.

- **STRONG**: containment plus identity evidence;
- **POSSIBLE**: a spatial candidate plus partial/exact identity evidence, but not strong;
- **NOT ENOUGH EVIDENCE**: proximity/containment without identity evidence.

| Population/category | Candidate points | Strong | Possible | Not enough evidence |
|---|---:|---:|---:|---:|
| SPb kindergarten | 36 | 0 | 6 | 30 |
| Global kindergarten | 65 | 0 | 10 | 55 |
| SPb school | 24 | 0 | 4 | 20 |
| Global school | 29 | 0 | 5 | 24 |
| Global clinic | 48 | 2 | 2 | 44 |
| Global hospital | 3 | 0 | 0 | 3 |
| Global pharmacy | 16 | 0 | 0 | 16 |

These are candidate point counts, not confirmed duplicate counts. The two strong clinic
cases are the only automatically convincing pairs under this intentionally narrow audit
rule; even they require category-aware lifecycle behavior before product conflation.

## Kindergarten deep dive

Inside the official city union there are 1,574 kindergarten objects: 326 Point, 1,239
Polygon, and 9 MultiPolygon. Of the points:

- 1 point is inside a same-category area;
- 35 area objects have a near-only same-category point, while 36 unique point objects
  have one or more same-category area candidates within 100 m (district-by-district
  counts overlap at boundaries and must not be summed);
- 320 are inside some building footprint; separately measured predicates include 11
  inside `building=kindergarten`, 308 inside generic/other buildings, and 1 inside a
  same-category amenity area, so these signals must not be treated as a disjoint
  partition;
- 6 have neither a containing building nor a same-category area within 100 m;
- strict candidates: 0 strong, 6 possible, 30 without sufficient identity evidence.

There are 1,248 area kindergartens in SPb. One contains a same-category point, 35 have a
same-category point within 100 m, and 1,212 have none within 100 m. Area-only objects are
therefore normal, not exceptional.

### Why is a kindergarten displayed as a Point?

For each of the 326 point kindergartens, the selected canonical source is an OSM node and
the map API returns that canonical node geometry. The frontend correctly renders the
returned Point. The production data distinguishes several cases:

1. **Only useful facility representation is the point:** six points have no containing
   building and no same-category area within 100 m; many more have only a generic
   containing building, which is not a facility geometry.
2. **Point plus plausible facility area:** 36 points have a same-category area within
   100 m, but none passes the strict strong tier and only six have supporting identity
   evidence.
3. **Point plus building footprint:** 11 points are inside a
   `building=kindergarten`; this is richer shape data but does not by itself prove that
   the building and POI are the same logical object or that the building represents the
   full facility site.
4. **Area is a different facility/site:** 30 candidate points have proximity without
   adequate identity evidence; examples include different kindergarten numbers.
5. **Classification gap:** building-only facility semantics are not selected by the
   current amenity-based category rules. This is relevant evidence, but changing the
   category rule would add building footprints as separate canonical objects, not solve
   entity identity.
6. **API/display behavior:** the API exposes source canonical geometry only and the
   frontend renders it correctly. The missing concept is a linked display/analysis
   representation, not a rendering defect.

The main causes are **B + D + E + F**, with legitimate **A** cases and a limited
classification component. There is no evidence of a broad **G** geometry bug.

## School deep dive

SPb has 1,061 school objects: 92 Point and 969 area (961 Polygon, 8 MultiPolygon).
Twenty-four points have a same-category area within 100 m: six are contained and 18 are
near-only; 68 have none. The tier result is 0 strong, 4 possible, and 20 without enough
evidence. Five area objects contain a point, 20 further areas have a nearby point, and
944 areas have no point within 100 m.

The policy can share the representation-role architecture with kindergarten, but not a
single matching rule. School campuses, departments, and differently named educational
units make proximity and containment particularly ambiguous. Causes are **B + D + E +
F**, with **A** and multi-entity campus cases.

## Healthcare deep dive

- **Hospital:** 170 SPb objects; 14 Point, 154 Polygon, 2 MultiPolygon. Hospital sites are
  usually area-shaped, but the three global node/area candidates have no adequate
  identity evidence. Prefer linked facility site, then facility building, then point.
- **Clinic:** 677 SPb objects; 510 Point and 167 Polygon. Clinics are frequently suites,
  departments, or co-located services. Two global point/area pairs have strong evidence,
  but most containing buildings are generic and 44/48 nearby candidates lack identity
  evidence. Link only with stronger category-aware evidence.
- **Pharmacy:** 2,404 SPb objects; 2,371 Point and 33 Polygon. A POI point is normally the
  correct representation for a shop/service within a larger building. None of 16 global
  nearby-area candidates has supporting identity evidence. Do not force area geometry.

Healthcare therefore needs category-specific semantics. Hospital may prefer a site;
clinic must preserve subfacility identity; pharmacy is mostly good as a Point.

## Parks and water

Parks are cleanly area-based: 1,573 in SPb, all Polygon/MultiPolygon and all valid. Their
source area is appropriate for display and analysis. No point or line anomaly exists.

Water is structurally valid but intentionally mixed: polygonal `natural=water` features
and linear `waterway=river` ways. The known limitation is semantic coverage, not invalid
canonical geometry. Exhaustive water enrichment remains separate work and is not S4R.

## Roads and transport stops

Every road is a valid OSM-way LineString and every categorized stop is an OSM-node
Point. Road ways are intentionally segmented; segments sharing a name are not facility
duplicates. Street grouping belongs to S5. Stops include overlapping OSM transport
semantics (globally: 7,770 `highway=bus_stop`, 10,822 `stop_position`, 7,663
`public_transport=platform`, and 952 `tram_stop`), so counts must not be added. Platform
and route redesign is deferred to the transport model; the current category has no
unexpected geometry.

## Administrative boundaries

All 791 generic administrative objects are valid relation-derived Polygon/MultiPolygon.
The 18 authoritative district registry objects remain separate stable bindings and are
the only authority for district selection and overlay. No boundary or district model
change is justified by this audit.

## Real inspected cases

Classification below describes the point/area relationship, not a production merge
decision. `BUILDING ONLY` means that the source Point is retained because a generic
footprint is not a facility identity.

### Kindergartens

| District | Point OSM / name | Area OSM / name | Relation and tags | Class / recommendation |
|---|---|---|---|---|
| Калининский | node/2472060666, Детский сад № 22 | way/1413226296, Детский сад № 22 | Polygon site, 12.4 m; normalized name/ref | POSSIBLE; preserve both, review/link |
| Калининский | node/4472592484, ДРЦ Знайка | way/1334965786, Детский сад №54 | Polygon site, 35.6 m; different identity | NOT ENOUGH; preserve both |
| Колпинский | node/13176623095, Bambika club | way/38020766 | containing generic building | BUILDING ONLY; keep Point |
| Курортный | node/7304462485, Саншайн кидс | way/709814973 | containing generic building | BUILDING ONLY; keep Point |
| Курортный | node/12271667994, Детский сад №30 | way/189277416 | containing generic building | BUILDING ONLY; keep Point |
| Приморский | node/11985468578, Дважды Два | way/825472402, Детский сад №56 | Polygon site, 12.2 m; different name/ref | NOT ENOUGH; preserve both |
| Приморский | node/10095834017, Жили-Были Мы | relation/9984979, Детский сад №47 | Polygon site, 37.5 m; different identity | NOT ENOUGH; preserve both |
| Пушкинский | node/1297487017, Детский сад №28 | way/1316842939, unnamed | contained; area has facility category, point has ref/address | NOT ENOUGH; preserve pending identity evidence |
| Пушкинский | node/4813244149, Частный детский сад «Минутка» | way/119353220, Детский сад №39 | Polygon site, 79.8 m | NOT ENOUGH; preserve both |
| Центральный | node/3583782889, Детский сад №115 | way/628426559, same name/ref | Polygon site, 68.2 m | POSSIBLE; representation-group candidate |
| Центральный | node/5265188406, Детский сад №250 | way/91757471, same name/ref | Polygon site, 70.3 m | POSSIBLE; representation-group candidate |

### Schools

| District | Point OSM / name | Area OSM / name | Evidence | Class / recommendation |
|---|---|---|---|---|
| Адмиралтейский | node/4723897632, Деловая волна | relation/11000460, Школа №307 | contained, different identity | NOT ENOUGH; preserve both |
| Василеостровский | node/10572406221, Аспект | way/816881051, Дошкольное отделение школы №35 | contained, different unit | NOT ENOUGH; preserve both |
| Кировский | node/7207858323, Школа №658 | way/396726888, Школа №269 | contained, conflicting ref | NOT ENOUGH; preserve both |
| Колпинский | node/12945082113, Эль-Ниньо | way/86164794 | generic containing building | BUILDING ONLY; keep Point |
| Кронштадтский | node/13201044401, Школа425 | way/131755391 | generic containing building | BUILDING ONLY; keep Point |
| Курортный | node/6700335278, unnamed | way/37886307 | generic containing building | BUILDING ONLY; keep Point |
| Петродворцовый | node/10015599214, Воскресная школа | relation/9082266, Петергофская гимназия | 53.2 m, different institution | NOT ENOUGH; preserve both |
| Приморский | node/4611740491, Школа №46 | way/147473968, unnamed | contained, insufficient tags | NOT ENOUGH; preserve both |
| Пушкинский | node/10225419217, Школа-интернат №16 | way/228896584, Школа №500 | 30.5 m, conflicting ref | NOT ENOUGH; preserve both |
| Центральный | node/2580869526, Школа Герценовского университета | way/827140615, Гимназия №209 | 19.9 m, different institution | NOT ENOUGH; preserve both |

### Hospitals

| District | Point | Nearby/containing area | Assessment |
|---|---|---|---|
| Выборгский | node/674371094, Противотуберкулезный диспансер №11 | relation/1768597, Городская туберкулёзная больница №2 | Same site, different institution semantics; not enough |
| Петроградский | node/8519106718, Госпиталь управления ФСБ | relation/12139698, Областная больница №31, 81.6 m | Proximity only; not enough |
| Адмиралтейский | node/13125036345, Центр по профилактике и борьбе со СПИД | way/222657245, generic building | Building only; retain Point |
| Колпинский | node/649201015, Колпинский противотуберкулезный диспансер №4 | way/37728733, generic building | Building only; retain Point |
| Красносельский | node/5501300120, Балтийская Жемчужина | no supported facility area candidate | Source-limited Point |

### Clinics

| District | Point | Nearby/containing area | Assessment |
|---|---|---|---|
| Выборгский | node/1868505732, Поликлиника №104 | way/23375678, same address | STRONG diagnostic candidate; conservative link |
| Красногвардейский | node/10807428892, СМ-Клиника | way/751143097, same name/site | STRONG diagnostic candidate; conservative link |
| Адмиралтейский | node/8193687529, клиника Пирогова | relation/1835712, multiprofile centre | Containment without same entity; preserve both |
| Калининский | node/13618021604, Iclinic | way/60557410, центр планирования | Different service; preserve both |
| Красносельский | node/14100399291, clinic department | way/559011032, городская поликлиника №106 | Likely subfacility; preserve separate identity |

### Parks

| District | OSM identity / name | Geometry | Recommendation |
|---|---|---|---|
| Колпинский | relation/2424991, Колпинский парк | MultiPolygon | source area for display/analysis |
| Курортный | relation/2910991, Нижний парк | MultiPolygon | source area for display/analysis |
| Приморский | relation/5724145, Вокзальный сквер | MultiPolygon | source area for display/analysis |
| Пушкинский | relation/10331781, Жуковско-Волынский сквер | MultiPolygon | source area for display/analysis |
| Центральный | relation/21049867, бульвар Мстислава Ростроповича | MultiPolygon | source area for display/analysis |

## Distance semantics

Future distance/scoring must use geometry role, not a centroid:

| Geometry | Conceptual distance |
|---|---|
| Point | Geography distance to the point |
| Polygon | Distance to the covered area; 0 when the user is inside |
| MultiPolygon | Distance to the nearest component; 0 inside any component |
| LineString | Distance to the nearest point on the line |

`ST_PointOnSurface` remains useful for map navigation/labels but is analytically
misleading for large or concave areas. For site-distance semantics a user inside a
facility polygon should have distance 0. Building-distance and facility-site-distance
are different concepts and require explicit roles.

Measured examples use a hypothetical user at the area's point-on-surface:

| Pair | User → POI Point | User → area | Point-to-area gap |
|---|---:|---:|---:|
| clinic node/1868505732 ↔ way/23375678 | 22.8 m | 0 m | contained |
| kindergarten node/5265188406 ↔ way/91757471 | 105.3 m | 0 m | 70.3 m |
| kindergarten node/3583782889 ↔ way/628426559 | 93.6 m | 0 m | 68.2 m |
| clinic node/10807428892 ↔ way/751143097 | 11.2 m | 0 m | contained |

The difference is material for future scoring, but only after the entity/role link is
supported by evidence.

## Category expectations and verdict

| Category | Preferred display/analysis class | Acceptable fallback | Unexpected | Verdict / cause |
|---|---|---|---|---|
| school | linked facility site; then proven facility building | Point | line | Needs logical entity/dedup; B/D/E/F |
| kindergarten | linked facility site; then proven facility building | Point | line | Needs logical entity/dedup; A/B/D/E/F, limited rule gap |
| hospital | linked facility site; then proven facility building | Point | line | Multiple causes; A/B/D/E/F |
| clinic | source Point unless an entity link is strong | facility site/building | line | Category-specific logical link; A/B/D/E/F/H |
| pharmacy | Point | categorized shop area | line | Good/source-limited; forcing building is wrong |
| park | Polygon/MultiPolygon | none | point/line | Good as-is |
| water | source polygon or categorized waterway line | none | point | Structurally good; semantic enrichment separate |
| stop | Point | none in current category | area/line | Good as-is; future transport source separate |
| road | LineString segments | none | point/area | Good as-is; street entity belongs to S5 |
| administrative boundary | relation Polygon/MultiPolygon | none | point/line | Good as-is; district registry remains authority |

## Source, display, and analysis geometry

One geometry cannot safely serve all purposes for every facility:

- **source geometry** is immutable provenance for the OSM node/way/relation identity;
- **display geometry** may be a conservatively linked facility site or building while
  selection still resolves to a logical product entity;
- **analysis geometry** expresses the measured concept (normally facility site for
  accessibility, possibly a Point for a suite-level clinic/pharmacy).

The existing canonical model safely preserves source identity and provenance, but its
single selected canonical geometry and one-object-per-source behavior cannot express
the cross-source logical facility on its own. A derived link/entity layer can be added
without destroying current UUIDs or bindings.

## Architecture options

| Option | Identity/provenance | API/search/scoring | Lifecycle and false-match risk | Verdict |
|---|---|---|---|---|
| A. Mutate canonical geometry | Obscures which source supplied the shape and makes a node look polygonal | Simple initially, ambiguous later | Reimport churn; unsafe when link is wrong | Reject |
| B. Display override | Preserves source object; useful for presentation | Adds geometry role but leaves duplicate search/entity semantics | Moderate; still needs link lifecycle | Insufficient alone |
| C. Logical entity / representation group | Preserves all source UUIDs and provenance | One product identity can choose display and analysis roles while exposing sources | Best lifecycle model; must use conservative category rules and auditable evidence | **Recommend** |
| D. Client-side dedup | Source data untouched | Map, search, details, and scoring disagree | Hidden heuristics, stale links, highest false-match risk | Reject |

Recommended S4R shape: a derived logical facility/representation layer that links source
canonical objects, records role and evidence, preserves source UUIDs, and allows separate
display and analysis choices. Exact table names and schema belong to S4R design, not this
audit. Auto-link only strong evidence; retain possible candidates for review or stronger
signals. Never auto-link by proximity or generic-building containment alone.

## API implications

Today `GET /api/map/features` exposes `catalog.objects.geom`, object details are tied to
the canonical UUID, and search returns that UUID plus the canonical geometry type, bbox,
and representative point. If S4R is accepted:

- map results need an explicit display geometry and role (or a versioned replacement for
  current `geometry`), plus a logical entity identifier where applicable;
- ObjectCard should resolve the logical selection while retaining auditable source UUIDs;
- selection must not alternate between node and area representations of one entity;
- source geometry must remain available internally/provenance-wise rather than being
  overwritten.

The exact compatibility contract should be designed in S4R. No API is changed here.

## Search implications

A linked school/kindergarten should normally produce one product result rather than both
node and area rows, while clinics may legitimately retain subfacility results. Facility
representation linking and S5 street grouping are independent problems: S4R must not
group road segments or implement fuzzy production name matching.

## Scoring implications

Future scoring must choose a role-aware analysis geometry, perform geography distance to
the actual shape, and record which source/role produced the measurement. Site polygons
yield 0 for a user inside the site; centroid distance must not replace shape distance.
Unlinked or ambiguous facilities continue to use their canonical Point rather than an
unproven nearby building.

## Root-cause summary

| Category | Classification |
|---|---|
| Kindergarten | Mixed A/B/D/E/F; limited building-only classification gap; no broad G |
| School | B/D/E/F plus legitimate independent campus/unit identities |
| Hospital | A/B/D/E/F; too little evidence for automatic node/area conflation |
| Clinic | H: many valid Point subfacilities, two strong link candidates, generic buildings common |
| Pharmacy | Mostly A/F and legitimate point semantics; area coercion would be wrong |
| Park | Source and canonical area geometry correct |
| Water | Source/classification semantics incomplete, geometry pipeline correct |
| Stop | Source Point and rendering correct; transport conflation deferred |
| Road | Source way segmentation and LineString geometry correct; S5 owns street entity |
| Boundary | Relation assembly/canonical geometry correct; district registry stable |

## Remediation decision

**F5.5-S4R is needed: Logical Facility Entity / Representation Group with role-aware
Display and Analysis Geometry.**

This combines the useful part of a display override with a lifecycle-safe logical entity.
It is preferred over mutating canonical geometry because current source identities and
UUIDs are correct. It is preferred over frontend dedup because map, details, search, and
future scoring must share one auditable decision. Rules must be category-specific and
conservative, with strong/possible evidence tiers and no automatic generic-building
substitution.

S4R is a recommendation only. It is not implemented in F5.5-S4.
