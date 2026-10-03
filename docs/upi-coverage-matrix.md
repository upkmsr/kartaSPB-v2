# UPI source coverage matrix

Status reflects source discovery on 2026-10-03, not implemented product capability.
`FOUND SOURCE` means at least one official source is identified; it does not mean that
terms, history, vector access, or an adapter are complete.

## Mandatory source families

| Family | Status | Best official evidence | Discovery conclusion |
|---|---|---|---|
| General Plan | FOUND SOURCE | `UPI-SPB-GP-ACT`, `UPI-KGA-GIS` | Normative 2023 act plus current official GIS layers |
| PZZ | FOUND SOURCE | `UPI-SPB-PZZ-ACT`, `UPI-KGA-PZZ-CONSTRAINTS` | Normative act/amendments and PZZ 2025 map layers |
| PPT/PMT | FOUND SOURCE | `UPI-KGA-DPT-GIS`, `UPI-KGA-ISOGD-EXTRACT` | Public raster geometry; official vector/document extracts are request-based |
| GPZU | PARTIAL | `UPI-KGA-ISOGD-EXTRACT` | Explicitly available from ISOGD service; no public machine registry found |
| AGO | FOUND SOURCE | `UPI-KGA-AGO-GIS`, `UPI-KGA-ISOGD-EXTRACT` | Public official layer and official decision extract route; attributes remain partial |
| Construction permits | FOUND SOURCE | `UPI-TORIS-CONSTRUCTION` | Structured permit table with document IDs, dates, status and parent keys |
| Commissioning | FOUND SOURCE | `UPI-TORIS-CONSTRUCTION` | Structured commissioning table with parent keys |
| Construction supervision/status | FOUND SOURCE | `UPI-TORIS-CONSTRUCTION` | Point/polygon features with GUID/ROOTID and status |
| Land activity | FOUND SOURCE | `UPI-GIS-TORGI`, `UPI-KIO-AUCTIONS` | Machine lot registry plus city authority publications |
| Auctions/lease/sale | FOUND SOURCE | `UPI-GIS-TORGI`, `UPI-KIO-AUCTIONS` | Structured lots; SPb field/filter contract still needs adapter proof |
| Parcel/cadastral context | PARTIAL | `UPI-NSPD-PKK` | Official map and cadastral IDs; no sanctioned bulk API/terms established |
| Industrial zones | FOUND SOURCE | `UPI-KGA-GIS` | General Plan functional/production zones in official GIS |
| Grey belt | PARTIAL | `UPI-KGA-KRT`, General Plan/PZZ | KRT and production zones exist; no authoritative “grey belt” entity dataset found |
| KRT/redevelopment | FOUND SOURCE | `UPI-KGA-KRT` | Explicit PZZ 2025 KRT polygon layer plus legal publications |
| Height restrictions | FOUND SOURCE | `UPI-KGA-PZZ-CONSTRAINTS` | Height regulation and airport/Pushkin height constraint layers |
| Heritage/protection | FOUND SOURCE | `UPI-KGIOP-820`, `UPI-KGA-PZZ-CONSTRAINTS` | Normative law plus official GIS representation |
| Future transport | FOUND SOURCE | `UPI-KGA-GP-INFRA` | Streets, road structures, public transport, rail and facilities |
| Future social infrastructure | FOUND SOURCE | `UPI-KGA-GP-INFRA` | Education, health, sport, social service and public-space layers |
| Flood/water constraints | FOUND SOURCE | `UPI-KGA-PZZ-CONSTRAINTS` | Flood/submergence and water-protection layers |
| Environmental monitoring | PARTIAL | `UPI-INFOECO-AIR` | Official monitoring exists; no working machine endpoint established |
| Wind observations/climate | PARTIAL | `UPI-HYDROMET-CLIMATE` | Official observations and old normals; no verified wind-rose API/dataset |
| Dominants/skyline | PARTIAL | `UPI-KGA-SKYLINE`, `UPI-KGIOP-820` | Official silhouette/restriction geometry; named-dominant inventory/viewsheds absent |

## UPI capability/work-package coverage

| Capability | Status | Sources / required derivation | Important limitation |
|---|---|---|---|
| Official Planning Layers | FOUND SOURCE | KGA General Plan, PZZ, DPT and KRT GIS | Mostly raster-only public delivery |
| Historical Snapshots | FUTURE RESEARCH REQUIRED | legal amendment chains | No general machine snapshot archive found |
| Development Sites | DERIVED ONLY | join land, planning, AGO, permits and construction | No official cross-stage site identity |
| Development Events | DERIVED ONLY | normalize registry/document state changes | Needs snapshot/evidence pipeline |
| Stage Engine evidence | PARTIAL | Torgi, DPT, AGO, permits, construction, commissioning | Cross-source joins are incomplete |
| Land Activity | FOUND SOURCE | GIS Torgi and KIO | Geometry/city-filter contract needs validation |
| Planning Documents | FOUND SOURCE | DPT GIS, ISOGD service, official publications | Public vector/document index not unified |
| GPZU | PARTIAL | requested ISOGD extract | Restricted/paid request route |
| AGO | FOUND SOURCE | AGO GIS and requested decision extract | Public layer identifiers/dates unverified |
| Permit Progression | FOUND SOURCE | TORIS permit/commissioning tables | Revision/history semantics unverified |
| Construction Status | FOUND SOURCE | TORIS construction object service | Meaning/authority for every status needs contract |
| Height Intelligence | PARTIAL | PZZ GIS and Law 820-7 | Rules split across GIS and legal annexes |
| Viewsheds / Dominants | DERIVED ONLY | official restriction geometry as input | No official computed viewshed source found |
| Industrial / Grey Belt | PARTIAL | General Plan zones, KRT polygons | “Grey belt” must be a transparent derived concept |
| Wind / Climate | PARTIAL | Hydromet observations/normals, city monitoring | No citywide wind field or current wind-rose dataset |
| Time UI support | DERIVED ONLY | normalized events/snapshots | S7 has metadata but no time controls |
| Provenance | FOUND SOURCE | all primary URLs, IDs and documents | Product evidence model is not implemented |
| Data Quality Monitoring | DERIVED ONLY | source health/schema baselines | No monitoring jobs in UPI-1 |
| Incremental Refresh | PARTIAL | ArcGIS/Torgi stable IDs allow polling | No publisher delta feeds discovered |
| Combined Analysis | DERIVED ONLY | spatial/identity joins across normalized sources | Source semantics and licensing must remain visible |
| Change Feed | DERIVED ONLY | events from snapshots/documents | Direct official change feed not found |
| Development Timeline | DERIVED ONLY | evidence-ordered events | Must tolerate missing stages and contradictory dates |
| Evidence Graph | PARTIAL | cadastral IDs, document numbers, GUID/ROOTID, address/spatial joins | Only permit↔construction joins are directly proven |
| Dormant/Cancelled Projects | PARTIAL | Torgi/permit/construction statuses | No authoritative unified cancellation state |
| Geometry Evolution | DERIVED ONLY | retained normalized snapshots | WMS imagery is inadequate for robust geometry diff |
| Spatial Intersection | DERIVED ONLY | future PostGIS analysis | Must distinguish source fact from computed relation |
| Planning Context Card | DERIVED ONLY | General Plan/PZZ/protection intersections | Requires vectorization/licensing resolution |
| Historical Map | FUTURE RESEARCH REQUIRED | archived acts/snapshots | No complete official machine archive |
| Compare Mode | DERIVED ONLY | normalized snapshots | No UI or diff engine yet |
| Future Infrastructure | FOUND SOURCE | General Plan 2023 GIS | Planned does not mean committed/scheduled |
| Infrastructure Impact | DERIVED ONLY | proximity/intersection with planned infrastructure | Methodology and uncertainty required |
| Industrial Transformation | PARTIAL | KRT + production zones + development events | No official transformation lifecycle dataset |
| 3D/Height foundation | PARTIAL | height/protection rules | Building heights/surfaces and 3D rights unresolved |
| Parcel ↔ auction | PARTIAL | cadastral numbers in lots | NSPD automated parcel geometry not approved |
| Parcel ↔ zoning | DERIVED ONLY | cadastral geometry intersect PZZ | Requires lawful parcel geometry access |
| Parcel ↔ planning document | PARTIAL | DPT parcel layers and document numbers | Stable public feature identifiers not verified |
| Parcel ↔ permit | PARTIAL | permit cadastral number/address | Field population/completeness needs profiling |
| Source health | DERIVED ONLY | probe baselines | Monitoring intentionally not implemented |

## Coverage interpretation

- Strongest immediately automatable official evidence: TORIS construction objects and
  permit/commissioning tables, and GIS Torgi lots.
- Strongest immediately visible official geography: KGA General Plan, PZZ, constraints,
  DPT and KRT WMS layers.
- Weakest required areas: reusable cadastral parcel geometry, historical spatial
  versions, public GPZU access, wind roses, named skyline dominants and official viewsheds.
- “Derived only” is intentional: development sites, stages, impacts, viewsheds and
  change feeds are KARTASPB interpretations and must never be presented as source facts.
