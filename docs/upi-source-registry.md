# UPI official source registry

Verified 2026-10-03 for UPI-1. This is a discovery registry, not an ingestion
configuration. No entry grants permission to ingest or republishes a provider's data.

## Classification

- `NORMATIVE_OFFICIAL`: a published legal act or its official annexes.
- `OFFICIAL_REGISTER`: an official record system or extract whose records carry the
  publisher's administrative meaning.
- `OFFICIAL_INFORMATIONAL`: official information, but not itself a legal register.
- `OFFICIAL_GIS`: an official spatial representation; legal force remains with the
  underlying act or register unless the publisher says otherwise.
- `SECONDARY_REFERENCE`: useful corroboration, never a replacement for a primary source.
- `DERIVED_NOT_SOURCE`: a future KARTASPB computation, not external evidence.

Automation levels are `A` stable machine service/API, `B` structured download, `C`
structured registry requiring an adapter, `D` document extraction, `E` browser/manual,
and `F` inaccessible or restricted. Change suitability is `DIRECT_DIFF`,
`SNAPSHOT_DIFF`, `DOCUMENT_EVENT`, `MANUAL_COMPARE`, or `NOT_DIFFABLE`.

Priority means implementation suitability, not legal or civic importance: `P0` is a
first implementation candidate; `P1` valuable after a source adapter and evidence
model; `P2` research/manual support; `P3` defer.

## Registry

### UPI-SPB-GP-ACT — General Plan 2023 publication

- `source_id`: `UPI-SPB-GP-ACT`.
- `title`: General Plan of Saint Petersburg (2023); `publisher`: Administration of
  Saint Petersburg / Committee for Urban Development and Architecture (KGA);
  `publisher_role`: official city publisher and planning authority.
- `official_status`: `NORMATIVE_OFFICIAL`; `source_family`: General Plan.
- `primary_url`: [official General Plan page](https://www.gov.spb.ru/gov/otrasl/ingen/generalnyj-plan-sankt-peterburga/);
  `documentation_url`: same; `service_url`: null; `service_type`: official web
  publication and legal-document links; `format`: HTML/PDF legal materials.
- `access_mode`: public browser/download; `authentication`: none observed;
  `license_or_terms`: public legal publication, reuse terms not separately verified.
- `geometry_available`: in official annexes and separately in KGA GIS; `geometry_type`:
  mixed thematic maps; `crs`: unknown in documents; `spatial_extent`: Saint Petersburg.
- `temporal_information`: plan adopted 2023; `version_field`: law/version in publication;
  `publication_date_field`: present in legal act; `update_date_field`: page metadata;
  `status_field`: legal-act status; `historical_versions`: legal publication history,
  not a machine snapshot archive.
- `object_identifier`: null; `document_identifier`: Saint Petersburg Law No. 785-169;
  `update_frequency_observed`: event-driven; `update_frequency_claimed`: unknown.
- `automation_level`: `D`, because the authority is document-based;
  `pagination_or_download_method`: linked documents; `estimated_volume`: small set of
  large annexes; `change_suitability`: `DOCUMENT_EVENT`.
- `schema_notes`: text plus cartographic annexes; `quality_notes`: normative source but
  not a feature API; `legal_authority_notes`: authoritative act, unlike the convenient
  GIS rendering; `known_limitations`: difficult object-level diff.
- `candidate_layer_class`: none directly; `candidate_loading_strategy`: manual;
  `candidate_selection_kind`: none; `candidate_time_model`: event;
  `provenance_kind`: official.
- `early_signal_value`: low (`PLANNING`, citywide policy); `implementation_priority`:
  `P1` as evidence/version anchor; `verification_status`: verified official page;
  `last_verified_at`: 2026-10-03.

### UPI-KGA-GIS — Open ISOGD / KGA map

- `source_id`: `UPI-KGA-GIS`.
- `title`: Open ISOGD KGA map; `publisher`: KGA; `publisher_role`: official planning
  authority and ISOGD operator.
- `official_status`: `OFFICIAL_GIS`; `source_family`: General Plan, PZZ, PPT/PMT, AGO,
  permits, restrictions, future infrastructure.
- `primary_url`: [KGA map](https://portal.kgainfo.spb.ru/KGAMap/);
  `documentation_url`: [official KGA description](https://www.gov.spb.ru/gov/otrasl/architecture/news/305793/);
  `service_url`: [public layer registry](https://portal.kgainfo.spb.ru/KGAMap/Map/GetLayers);
  `service_type`: JSON layer registry plus proxied WMS/WMTS; `format`: JSON and PNG.
- `access_mode`: public; `authentication`: none for inspected routes;
  `license_or_terms`: public but terms unclear.
- `geometry_available`: yes as rendered GIS layers; `geometry_type`: mixed point/line/
  polygon; `crs`: WMS accepts EPSG:3857; `spatial_extent`: Saint Petersburg.
- `temporal_information`: product generations appear in layer names (`GP2023v2`,
  `PZZ_2025`); `version_field`: layer name only; `publication_date_field`: not exposed;
  `update_date_field`: `ActualDate` exists but was empty on inspected layers;
  `status_field`: layer-specific/unknown; `historical_versions`: not exposed as snapshots.
- `object_identifier`: layer-specific, feature IDs not exposed by registry;
  `document_identifier`: layer/product IDs; `update_frequency_observed`: unknown;
  `update_frequency_claimed`: unknown.
- `automation_level`: `A` for layer discovery and map images, not feature extraction;
  `pagination_or_download_method`: `GetLayers`, WMS `GetMap`; `estimated_volume`: 361 KB
  layer registry, hundreds of layer declarations; `change_suitability`: `SNAPSHOT_DIFF`
  only for image/layer metadata unless a sanctioned vector route is supplied.
- `schema_notes`: inspected records include `layerID`, visibility, scale, opacity,
  access/edit/export flags; `ExportLayer=false` on tested planning layers;
  `quality_notes`: working map endpoint, but `GetCapabilities` returned 204;
  `legal_authority_notes`: GIS is reference representation; cite its underlying act;
  `known_limitations`: no verified WFS/vector export, blank dates, local TLS chain warning.
- `candidate_layer_class`: `raster`; `candidate_loading_strategy`: tiles/manual proxy;
  `candidate_selection_kind`: none; `candidate_time_model`: snapshot;
  `provenance_kind`: official.
- `early_signal_value`: medium across `PLANNING`, `DESIGN`, and `PERMIT` layers;
  `implementation_priority`: `P0` for a bounded visual pilot, `P1` for intelligence;
  `verification_status`: JSON registry 200 and 256 px WMS map 200;
  `last_verified_at`: 2026-10-03.

### UPI-SPB-PZZ-ACT — current PZZ publication

- `source_id`: `UPI-SPB-PZZ-ACT`.
- `title`: Rules for Land Use and Development of Saint Petersburg (PZZ);
  `publisher`: Government of Saint Petersburg / KGA; `publisher_role`: rule-making and
  planning authority.
- `official_status`: `NORMATIVE_OFFICIAL`; `source_family`: PZZ/zoning.
- `primary_url`: [official PZZ commission page](https://www.gov.spb.ru/gov/otrasl/architecture/current_activities/groups/komissiya-po-zemlepolzovaniyu-i-zastrojke-sankt-peterburga/);
  `documentation_url`: [official 2025 amendment announcement](https://www.gov.spb.ru/press/governor/309021/);
  `service_url`: null; `service_type`: official legal publication; `format`: HTML/PDF.
- `access_mode`: public; `authentication`: none; `license_or_terms`: public legal
  publication, reuse terms not separately verified.
- `geometry_available`: cartographic annexes and separately in KGA GIS;
  `geometry_type`: polygon/rule maps; `crs`: unknown in documents;
  `spatial_extent`: Saint Petersburg.
- `temporal_information`: amendments to Resolution No. 524; `version_field`: act number/
  amendment; `publication_date_field`: yes; `update_date_field`: page date;
  `status_field`: legal act; `object_identifier`: zone codes in annexes;
  `document_identifier`: Government Resolution No. 524.
- `historical_versions`: legal amendment chain; `update_frequency_observed`: event-driven;
  `update_frequency_claimed`: unknown; `automation_level`: `D`;
  `pagination_or_download_method`: documents; `estimated_volume`: multi-annex act;
  `change_suitability`: `DOCUMENT_EVENT`.
- `schema_notes`: zoning maps plus regulations; `quality_notes`: normative but not a
  feature service; `legal_authority_notes`: authority is the current act;
  `known_limitations`: consolidated object-level change extraction is non-trivial.
- `candidate_layer_class`: none directly; `candidate_loading_strategy`: manual;
  `candidate_selection_kind`: none; `candidate_time_model`: event;
  `provenance_kind`: official.
- `early_signal_value`: high `PLANNING` when amendments occur;
  `implementation_priority`: `P1` evidence anchor; `verification_status`: verified;
  `last_verified_at`: 2026-10-03.

### UPI-KGA-ISOGD-EXTRACT — requested ISOGD information

- `source_id`: `UPI-KGA-ISOGD-EXTRACT`.
- `title`: Provision of information from Saint Petersburg ISOGD; `publisher`: KGA via
  Saint Petersburg public services; `publisher_role`: official register custodian.
- `official_status`: `OFFICIAL_REGISTER`; `source_family`: PPT/PMT, GPUZ, AGO, permits,
  commissioning.
- `primary_url`: [official service card](https://gu.spb.ru/188547/);
  `documentation_url`: [KGA warning and scope](https://www.gov.spb.ru/gov/otrasl/architecture/news/305793/);
  `service_url`: null; `service_type`: application-based register extract;
  `format`: documents and, where requested, vector models.
- `access_mode`: request/paid service; `authentication`: applicant workflow;
  `license_or_terms`: restricted to service terms.
- `geometry_available`: potentially yes in requested vector models; `geometry_type`:
  varies; `crs`: unknown until delivery; `spatial_extent`: request-defined.
- `temporal_information`: register content at fulfillment time; `version_field`: unknown;
  `publication_date_field`: document-specific; `update_date_field`: unknown;
  `status_field`: document-specific; `object_identifier`: request/document-specific;
  `document_identifier`: official document number where supplied.
- `historical_versions`: potentially obtainable case-by-case, not public API;
  `update_frequency_observed`: continuous register; `update_frequency_claimed`: unknown;
  `automation_level`: `F`; `pagination_or_download_method`: formal request;
  `estimated_volume`: request-dependent; `change_suitability`: `MANUAL_COMPARE`.
- `schema_notes`: official card explicitly covers PPT/PMT, AGO decisions, GPUZ,
  construction and commissioning permits; `quality_notes`: authoritative extract;
  `legal_authority_notes`: official register response; `known_limitations`: fee, delay,
  authorization, no proven bulk automation.
- `candidate_layer_class`: `reference-vector` after lawful acquisition;
  `candidate_loading_strategy`: manual; `candidate_selection_kind`: layer-feature;
  `candidate_time_model`: snapshot; `provenance_kind`: official.
- `early_signal_value`: high `PLANNING`/`DESIGN`/`PERMIT`, but operationally restricted;
  `implementation_priority`: `P2`; `verification_status`: verified service card;
  `last_verified_at`: 2026-10-03.

### UPI-KGA-DPT-GIS — PPT/PMT spatial layers

- `source_id`: `UPI-KGA-DPT-GIS`.
- `title`: Open ISOGD planning-document layers; `publisher`: KGA;
  `publisher_role`: planning authority.
- `official_status`: `OFFICIAL_GIS`; `source_family`: PPT/PMT.
- `primary_url`: [KGA map](https://portal.kgainfo.spb.ru/KGAMap/);
  `documentation_url`: [official planning-procedure notice](https://www.gov.spb.ru/gov/otrasl/architecture/news/268763/);
  `service_url`: [layer registry](https://portal.kgainfo.spb.ru/KGAMap/Map/GetLayers);
  `service_type`: proxied WMS; `format`: JSON metadata/PNG map.
- `access_mode`: public map; `authentication`: none observed; `license_or_terms`: unclear.
- `geometry_available`: yes; `geometry_type`: polygon/line; `crs`: EPSG:3857 rendering;
  `spatial_extent`: Saint Petersburg.
- `temporal_information`: planning order numbers appear in some layer names;
  `version_field`: layer/order suffix; `publication_date_field`: not consistently exposed;
  `update_date_field`: blank in inspected metadata; `status_field`: unknown;
  `object_identifier`: unknown; `document_identifier`: order numbers in named layers.
- `historical_versions`: not exposed; `update_frequency_observed`: event-driven/unknown;
  `update_frequency_claimed`: unknown; `automation_level`: `A` raster only;
  `pagination_or_download_method`: WMS map; `estimated_volume`: many layers;
  `change_suitability`: `SNAPSHOT_DIFF` for layer imagery, `DOCUMENT_EVENT` via acts.
- `schema_notes`: verified layers include existing/planned planning elements, planned
  capital-construction zones, formed parcels, reservations/acquisitions and servitudes;
  `quality_notes`: geometry present but vector export disabled;
  `legal_authority_notes`: consult approving act; `known_limitations`: no public feature
  schema or stable object IDs verified.
- `candidate_layer_class`: `raster`; `candidate_loading_strategy`: tiles/manual;
  `candidate_selection_kind`: none; `candidate_time_model`: snapshot;
  `provenance_kind`: official.
- `early_signal_value`: high `PLANNING`; `implementation_priority`: `P1`;
  `verification_status`: verified in live layer registry; `last_verified_at`: 2026-10-03.

### UPI-KGA-AGO-GIS — AGO decisions

- `source_id`: `UPI-KGA-AGO-GIS`.
- `title`: ROSAGOO decisions layer; `publisher`: KGA; `publisher_role`: authority
  coordinating architectural and urban appearance.
- `official_status`: `OFFICIAL_GIS`; `source_family`: AGO/design approvals.
- `primary_url`: [KGA map](https://portal.kgainfo.spb.ru/KGAMap/);
  `documentation_url`: [official KGA services](https://www.gov.spb.ru/gov/otrasl/architecture/gosuslugi/);
  `service_url`: [layer registry](https://portal.kgainfo.spb.ru/KGAMap/Map/GetLayers);
  `service_type`: proxied WMS layer `GIS2:ISOGD_69_TYPE`; `format`: JSON/PNG.
- `access_mode`: public map; `authentication`: none observed; `license_or_terms`: unclear;
  `geometry_available`: yes; `geometry_type`: unknown; `crs`: EPSG:3857 rendering;
  `spatial_extent`: Saint Petersburg.
- `temporal_information`: decisions are dated documents, but date not exposed in layer
  metadata; `version_field`: unknown; `publication_date_field`: unknown;
  `update_date_field`: blank; `status_field`: unknown; `object_identifier`: unknown;
  `document_identifier`: decision number expected but unverified in public response.
- `historical_versions`: no public archive verified; `update_frequency_observed`: unknown;
  `update_frequency_claimed`: unknown; `automation_level`: `A` raster only;
  `pagination_or_download_method`: WMS; `estimated_volume`: unknown;
  `change_suitability`: `SNAPSHOT_DIFF`/`DOCUMENT_EVENT` after identifier validation.
- `schema_notes`: only layer presence confirmed; `quality_notes`: no vector schema;
  `legal_authority_notes`: underlying decision, not pixels, is evidence;
  `known_limitations`: identifiers/dates require a document adapter or ISOGD extract.
- `candidate_layer_class`: `raster`; `candidate_loading_strategy`: tiles/manual;
  `candidate_selection_kind`: none; `candidate_time_model`: event;
  `provenance_kind`: official.
- `early_signal_value`: high `DESIGN`; `implementation_priority`: `P1`;
  `verification_status`: verified layer declaration; `last_verified_at`: 2026-10-03.

### UPI-TORIS-CONSTRUCTION — construction objects and permits

- `source_id`: `UPI-TORIS-CONSTRUCTION`.
- `title`: RGIS/TORIS Construction Supervision service; `publisher`: Saint Petersburg
  city GIS, data credited to Committee for Construction; `publisher_role`: official GIS
  publisher for construction-supervision data.
- `official_status`: `OFFICIAL_GIS` with official register-derived tables;
  `source_family`: permits, commissioning, supervision, construction status.
- `primary_url`: [ArcGIS service](https://gis.toris.gov.spb.ru/arccod1031/rest/services/STROINADZOR/OBJ_STROITELSTVA_WGS84/MapServer);
  `documentation_url`: [official construction page](https://www.gov.spb.ru/helper/stroitelstvo/);
  `service_url`: same ArcGIS REST service; `service_type`: MapServer with Query/Data;
  `format`: Esri JSON/JSON/images.
- `access_mode`: public query; `authentication`: none observed; `license_or_terms`:
  public but terms unclear.
- `geometry_available`: yes; `geometry_type`: point and polygon; `crs`: EPSG:3857;
  `spatial_extent`: Saint Petersburg service extent.
- `temporal_information`: object `DATECREATE`; permit tables contain document creation,
  deadline and extension fields; `version_field`: no row version observed;
  `publication_date_field`: document date; `update_date_field`: object creation only;
  `status_field`: `STATUSOBJECT`/`STATUSDOCUMENT`.
- `object_identifier`: `GUID`/`ROOTID`; `document_identifier`: `NUMBERDOCUMENT` and
  `ROOTID`; `historical_versions`: no archive endpoint verified;
  `update_frequency_observed`: unknown; `update_frequency_claimed`: online information
  is described by the city, exact SLA unknown.
- `automation_level`: `A`; `pagination_or_download_method`: ArcGIS paged Query;
  `estimated_volume`: 324 current construction geometries, 6,834 permit rows, 6,747
  commissioning rows at verification; `change_suitability`: `SNAPSHOT_DIFF`.
- `schema_notes`: service also exposes ZOS, developer and marketing tables;
  `quality_notes`: stable IDs and relational `PARENT_GUID`/`PARENT_ROOTID` are promising;
  `legal_authority_notes`: GIS presentation must retain originating document evidence;
  `known_limitations`: attribution says Committee for Construction while permit authority
  is Gosstroynadzor; ownership and field semantics need publisher confirmation.
- `candidate_layer_class`: `temporal-vector`; `candidate_loading_strategy`: viewport or
  server-side tiles after an adapter; `candidate_selection_kind`: layer-feature;
  `candidate_time_model`: event/range; `provenance_kind`: official.
- `early_signal_value`: very high `PERMIT`, `CONSTRUCTION`, `COMMISSIONING`;
  `implementation_priority`: `P0`; `verification_status`: metadata and count-only queries
  passed; `last_verified_at`: 2026-10-03.

### UPI-KIO-AUCTIONS — city land/property auction publications

- `source_id`: `UPI-KIO-AUCTIONS`.
- `title`: KIO auction publications; `publisher`: Committee for Property Relations
  (KIO); `publisher_role`: city property/land authority.
- `official_status`: `OFFICIAL_REGISTER`; `source_family`: land lease/sale/auctions.
- `primary_url`: [KIO documents and auction sections](https://www.gov.spb.ru/gov/otrasl/kio/documents/);
  `documentation_url`: [official 2026 publication channels notice](https://www.gov.spb.ru/gov/otrasl/kio/news/315754/);
  `service_url`: null; `service_type`: structured HTML publications and documents;
  `format`: HTML/PDF.
- `access_mode`: public; `authentication`: none; `license_or_terms`: public but unclear;
  `geometry_available`: generally no; `geometry_type`: null; `crs`: null;
  `spatial_extent`: Saint Petersburg.
- `temporal_information`: auction dates and publication pages; `version_field`: notice/
  auction number; `publication_date_field`: yes; `update_date_field`: page date;
  `status_field`: auction/result text; `object_identifier`: cadastral number/address;
  `document_identifier`: auction/notice identifier.
- `historical_versions`: dated pages retained, completeness unknown;
  `update_frequency_observed`: event-driven; `update_frequency_claimed`: unknown;
  `automation_level`: `C`; `pagination_or_download_method`: section crawl/document
  adapter; `estimated_volume`: unknown; `change_suitability`: `DOCUMENT_EVENT`.
- `schema_notes`: includes address, area, intended use, starting price and platform in
  sample publications; `quality_notes`: official city scope;
  `legal_authority_notes`: publication channel is official; `known_limitations`: page
  formats vary and geometry requires cadastral/spatial linkage.
- `candidate_layer_class`: `temporal-vector` after normalization;
  `candidate_loading_strategy`: independent/viewport; `candidate_selection_kind`:
  layer-feature; `candidate_time_model`: event; `provenance_kind`: official.
- `early_signal_value`: very high `EARLY_LAND`; `implementation_priority`: `P1` because
  GIS Torgi is easier to automate; `verification_status`: verified official pages;
  `last_verified_at`: 2026-10-03.

### UPI-GIS-TORGI — federal public auction registry

- `source_id`: `UPI-GIS-TORGI`.
- `title`: GIS Torgi public lot registry; `publisher`: Federal Treasury;
  `publisher_role`: operator of the official Russian auction information system.
- `official_status`: `OFFICIAL_REGISTER`; `source_family`: auctions, land lease/sale.
- `primary_url`: [public lot registry](https://torgi.gov.ru/new/public/lots/reg);
  `documentation_url`: [Federal Treasury system description](https://roskazna.gov.ru/gis/gis-torgi-torgi-gov-ru);
  `service_url`: [public lot search API](https://torgi.gov.ru/new/api/public/lotcards/search?size=1&page=0);
  `service_type`: JSON search API; `format`: JSON.
- `access_mode`: public; `authentication`: none for tested search;
  `license_or_terms`: public official system, API/reuse terms unclear.
- `geometry_available`: sometimes location/address/attributes, map geometry not validated;
  `geometry_type`: unknown; `crs`: unknown; `spatial_extent`: Russian Federation.
- `temporal_information`: creation, publication, bidding end and statuses;
  `version_field`: composite lot ID/notice number; `publication_date_field`:
  `noticeFirstVersionPublicationDate`; `update_date_field`: `createDate` only in tested
  schema; `status_field`: `lotStatus`.
- `object_identifier`: composite lot `id`; `document_identifier`: `noticeNumber` and
  `lotNumber`; `historical_versions`: first-version date exposed, full revision history
  not tested; `update_frequency_observed`: active registry; `update_frequency_claimed`:
  unknown.
- `automation_level`: `A`; `pagination_or_download_method`: paged search API;
  `estimated_volume`: API reported a capped 10,000 results for an unfiltered query;
  `change_suitability`: `SNAPSHOT_DIFF` plus `DOCUMENT_EVENT`.
- `schema_notes`: structured bid type/form, status, category, attributes,
  characteristics, prices and region code; `quality_notes`: city filtering and cadastral
  field normalization still need a contract test; `legal_authority_notes`: official
  publication system; `known_limitations`: undocumented public endpoint and TLS-chain
  warning in this environment.
- `candidate_layer_class`: `temporal-vector`; `candidate_loading_strategy`: viewport;
  `candidate_selection_kind`: layer-feature; `candidate_time_model`: event;
  `provenance_kind`: official.
- `early_signal_value`: very high `EARLY_LAND`; `implementation_priority`: `P0` for an
  event adapter, not necessarily first visual demo; `verification_status`: size-one API
  request 200 JSON; `last_verified_at`: 2026-10-03.

### UPI-NSPD-PKK — cadastral context

- `source_id`: `UPI-NSPD-PKK`.
- `title`: National Spatial Data System public map; `publisher`: Rosreestr/Roskadastr;
  `publisher_role`: federal spatial/cadastral system operator.
- `official_status`: `OFFICIAL_INFORMATIONAL`; `source_family`: parcel/cadastral context.
- `primary_url`: [NSPD map](https://nspd.gov.ru/map); `documentation_url`:
  [Rosreestr](https://rosreestr.gov.ru/); `service_url`: null; `service_type`: public web
  map; `format`: browser application.
- `access_mode`: public map; `authentication`: not required for landing page;
  `license_or_terms`: unknown/review required.
- `geometry_available`: displayed; `geometry_type`: cadastral polygons/points and other
  thematic layers; `crs`: unknown; `spatial_extent`: Russian Federation.
- `temporal_information`: current public context; `version_field`: unknown;
  `publication_date_field`: unknown; `update_date_field`: unknown; `status_field`:
  layer-specific; `object_identifier`: cadastral number; `document_identifier`: null.
- `historical_versions`: not found; `update_frequency_observed`: unknown;
  `update_frequency_claimed`: unknown; `automation_level`: `E` until a documented API
  and terms are identified; `pagination_or_download_method`: browser search;
  `estimated_volume`: national; `change_suitability`: `NOT_DIFFABLE` as currently known.
- `schema_notes`: no sanctioned machine endpoint was established; `quality_notes`:
  suitable for confirmation/context, not a silent bulk source;
  `legal_authority_notes`: public map does not replace an EGRN extract;
  `known_limitations`: access, licensing and automated-use limits unresolved; local TLS
  chain required diagnostic `-k`.
- `candidate_layer_class`: none until terms/API resolved; `candidate_loading_strategy`:
  external/manual; `candidate_selection_kind`: none; `candidate_time_model`: none;
  `provenance_kind`: official.
- `early_signal_value`: medium as parcel join context, not a development event;
  `implementation_priority`: `P2`; `verification_status`: public map landing 200;
  `last_verified_at`: 2026-10-03.

### UPI-RGIS — Regional GIS and TORIS service directory

- `source_id`: `UPI-RGIS`.
- `title`: Regional Geoinformation System of Saint Petersburg; `publisher`: KIO / city
  information infrastructure; `publisher_role`: official integrator of spatial data
  from city authorities and organizations.
- `official_status`: `OFFICIAL_GIS`; `source_family`: cross-domain municipal GIS.
- `primary_url`: [RGIS](https://www.rgis.spb.ru/); `documentation_url`:
  [official RGIS access notice](https://www.gov.spb.ru/gov/otrasl/kio/news/307513/);
  `service_url`: [public ArcGIS REST directory](https://gis.toris.gov.spb.ru/arccod1031/rest/services?f=pjson);
  `service_type`: web GIS plus ArcGIS REST; `format`: HTML/JSON/Esri services.
- `access_mode`: public map and mixed public/authenticated functions;
  `authentication`: public map; ESIA required for organizational personal cabinet;
  `license_or_terms`: public but terms unclear.
- `geometry_available`: yes; `geometry_type`: mixed; `crs`: service-specific, inspected
  basemap and construction service use EPSG:3857; `spatial_extent`: Saint Petersburg.
- `temporal_information`: source-specific; `version_field`: service-specific;
  `publication_date_field`: source-specific; `update_date_field`: source-specific;
  `status_field`: source-specific; `object_identifier`: source-specific;
  `document_identifier`: source-specific.
- `historical_versions`: not generally exposed; `update_frequency_observed`: unknown;
  `update_frequency_claimed`: unknown; `automation_level`: `A` for public REST services;
  `pagination_or_download_method`: ArcGIS query; `estimated_volume`: directory contained
  multiple domain folders/services; `change_suitability`: `SNAPSHOT_DIFF` per service.
- `schema_notes`: root service catalog exposed construction, property-control and other
  folders; `quality_notes`: every subservice needs its own authority/terms review;
  `legal_authority_notes`: integrator display is not automatically normative;
  `known_limitations`: site TLS-chain warning, mixed publishers and access modes.
- `candidate_layer_class`: source-specific reference/temporal vector or raster;
  `candidate_loading_strategy`: viewport/tiles; `candidate_selection_kind`: layer-feature
  where stable ID exists; `candidate_time_model`: source-specific;
  `provenance_kind`: official.
- `early_signal_value`: high where official status layers exist;
  `implementation_priority`: `P0` platform, per-layer decision required;
  `verification_status`: homepage and REST directory 200;
  `last_verified_at`: 2026-10-03.

### UPI-SPB-OPEN-DATA — city open-data portal

- `source_id`: `UPI-SPB-OPEN-DATA`.
- `title`: Open Data Saint Petersburg; `publisher`: Committee for Informatization and
  Communications / Government of Saint Petersburg; `publisher_role`: city open-data
  system operator.
- `official_status`: `OFFICIAL_INFORMATIONAL`; `source_family`: cross-domain open data.
- `primary_url`: [official system description](https://www.gov.spb.ru/gov/otrasl/c_information/napravlenie-deyatelnosti-komiteta/otkrytye-dannye/);
  `documentation_url`: same; `service_url`: [portal](https://data.gov.spb.ru/);
  `service_type`: open-data portal; `format`: claimed machine-readable formats.
- `access_mode`: intended public; `authentication`: unknown; `license_or_terms`: open
  data by statutory purpose, dataset-specific terms not inspected.
- `geometry_available`: dataset-specific; `geometry_type`: unknown; `crs`: unknown;
  `spatial_extent`: Saint Petersburg.
- `temporal_information`: dataset-specific; `version_field`: unknown;
  `publication_date_field`: unknown; `update_date_field`: unknown; `status_field`:
  unknown; `object_identifier`: dataset-specific; `document_identifier`: dataset ID.
- `historical_versions`: unknown; `update_frequency_observed`: unknown;
  `update_frequency_claimed`: dataset-specific; `automation_level`: `F` at verification
  because the portal root returned 404; `pagination_or_download_method`: unknown;
  `estimated_volume`: unknown; `change_suitability`: `NOT_DIFFABLE` until restored.
- `schema_notes`: official description promises machine-readable datasets;
  `quality_notes`: no UPI-specific dataset was proven; `legal_authority_notes`: open data
  is informational unless backed by a register/act; `known_limitations`: current portal
  response blocked catalogue discovery.
- `candidate_layer_class`: none yet; `candidate_loading_strategy`: external/manual;
  `candidate_selection_kind`: none; `candidate_time_model`: none;
  `provenance_kind`: official.
- `early_signal_value`: unknown; `implementation_priority`: `P3` pending availability;
  `verification_status`: official description verified, portal root HTTP 404;
  `last_verified_at`: 2026-10-03.

### UPI-KGA-KRT — integrated-development territories

- `source_id`: `UPI-KGA-KRT`.
- `title`: PZZ 2025 KRT territories layer; `publisher`: KGA;
  `publisher_role`: planning authority.
- `official_status`: `OFFICIAL_GIS`; `source_family`: industrial/grey belt/KRT.
- `primary_url`: [KGA map](https://portal.kgainfo.spb.ru/KGAMap/);
  `documentation_url`: [official KRT information](https://www.gov.spb.ru/gov/terr/reg_kirovsk/stroitelstvo-v-rajone/kompleksnoe-razvitie-territorij-v-sankt-peterburge/);
  `service_url`: [layer registry](https://portal.kgainfo.spb.ru/KGAMap/Map/GetLayers);
  `service_type`: WMS layer `GIS2:PZZ_2025_P21_KRT_AREA`; `format`: JSON/PNG.
- `access_mode`: public map; `authentication`: none observed; `license_or_terms`: unclear;
  `geometry_available`: yes; `geometry_type`: polygon; `crs`: EPSG:3857 rendering;
  `spatial_extent`: Saint Petersburg.
- `temporal_information`: PZZ 2025 generation; `version_field`: product/layer name;
  `publication_date_field`: underlying act; `update_date_field`: blank;
  `status_field`: unknown; `object_identifier`: unknown; `document_identifier`:
  underlying PZZ/KRT act.
- `historical_versions`: legal acts, not GIS snapshots; `update_frequency_observed`:
  event-driven; `update_frequency_claimed`: unknown; `automation_level`: `A` raster;
  `pagination_or_download_method`: WMS; `estimated_volume`: unknown;
  `change_suitability`: `DOCUMENT_EVENT` plus future `SNAPSHOT_DIFF`.
- `schema_notes`: explicit KRT-area layer; `quality_notes`: no public vector attributes;
  `legal_authority_notes`: legal decisions control; `known_limitations`: “grey belt” is a
  broader analytical concept and must not be equated automatically with KRT polygons.
- `candidate_layer_class`: `raster` initially, `reference-vector` if lawful vectors;
  `candidate_loading_strategy`: tiles; `candidate_selection_kind`: none;
  `candidate_time_model`: snapshot; `provenance_kind`: official.
- `early_signal_value`: high `PLANNING`; `implementation_priority`: `P1`;
  `verification_status`: live layer declaration verified; `last_verified_at`: 2026-10-03.

### UPI-KGIOP-820 — heritage protection rules

- `source_id`: `UPI-KGIOP-820`.
- `title`: Saint Petersburg Law No. 820-7 and protection-zone maps;
  `publisher`: Government of Saint Petersburg / KGIOP; `publisher_role`: heritage
  protection authority and official legal publisher.
- `official_status`: `NORMATIVE_OFFICIAL`; `source_family`: height/protection.
- `primary_url`: [official publication reference](https://www.gov.spb.ru/gov/otrasl/c_govcontrol/news/205207/);
  `documentation_url`: [official legal document](https://npa.gov.spb.ru/SpbGovSearch/Document/40501.html);
  `service_url`: null; `service_type`: law and cartographic annexes; `format`: HTML/PDF.
- `access_mode`: public; `authentication`: none; `license_or_terms`: public legal
  publication, reuse terms not separately verified.
- `geometry_available`: yes in cartographic annexes and related KGA GIS layers;
  `geometry_type`: protection-zone polygons/lines; `crs`: document-specific unknown;
  `spatial_extent`: Saint Petersburg.
- `temporal_information`: amendments/effective dates; `version_field`: law revision;
  `publication_date_field`: yes; `update_date_field`: amendment publication;
  `status_field`: legal force; `object_identifier`: protection-zone/regime codes;
  `document_identifier`: Law No. 820-7.
- `historical_versions`: amendment chain; `update_frequency_observed`: event-driven;
  `update_frequency_claimed`: unknown; `automation_level`: `D`;
  `pagination_or_download_method`: annex documents; `estimated_volume`: large multi-part
  law; `change_suitability`: `DOCUMENT_EVENT`.
- `schema_notes`: protection boundaries, regimes and planning requirements;
  `quality_notes`: normative but complex to normalize; `legal_authority_notes`:
  authoritative source; `known_limitations`: multiple revisions and map annexes require
  legal/version review.
- `candidate_layer_class`: `reference-vector` after controlled extraction;
  `candidate_loading_strategy`: tiles; `candidate_selection_kind`: layer-feature;
  `candidate_time_model`: snapshot/event; `provenance_kind`: official.
- `early_signal_value`: medium contextual constraint; `implementation_priority`: `P1`;
  `verification_status`: official law/page verified; `last_verified_at`: 2026-10-03.

### UPI-KGA-PZZ-CONSTRAINTS — height, protection and flood GIS

- `source_id`: `UPI-KGA-PZZ-CONSTRAINTS`.
- `title`: PZZ 2025 constraint layers; `publisher`: KGA;
  `publisher_role`: official planning GIS publisher.
- `official_status`: `OFFICIAL_GIS`; `source_family`: height, heritage, airport,
  sanitary, water and flood constraints.
- `primary_url`: [KGA map](https://portal.kgainfo.spb.ru/KGAMap/);
  `documentation_url`: [official PZZ page](https://www.gov.spb.ru/gov/otrasl/architecture/current_activities/groups/komissiya-po-zemlepolzovaniyu-i-zastrojke-sankt-peterburga/);
  `service_url`: [layer registry](https://portal.kgainfo.spb.ru/KGAMap/Map/GetLayers);
  `service_type`: proxied WMS; `format`: JSON/PNG.
- `access_mode`: public map; `authentication`: none observed; `license_or_terms`: unclear;
  `geometry_available`: yes; `geometry_type`: polygon/line; `crs`: EPSG:3857 rendering;
  `spatial_extent`: Saint Petersburg.
- `temporal_information`: PZZ 2025 generation; `version_field`: layer generation;
  `publication_date_field`: underlying PZZ act; `update_date_field`: blank;
  `status_field`: constraint type; `object_identifier`: unknown;
  `document_identifier`: underlying acts.
- `historical_versions`: not in GIS; `update_frequency_observed`: event-driven/unknown;
  `update_frequency_claimed`: unknown; `automation_level`: `A` raster;
  `pagination_or_download_method`: WMS; `estimated_volume`: multiple citywide layers;
  `change_suitability`: `SNAPSHOT_DIFF`/`DOCUMENT_EVENT`.
- `schema_notes`: verified `VIS_REGL`, silhouette-influence, Pulkovo/Pushkin height,
  heritage, sanitary, water-protection and flood-zone layers; `quality_notes`: strong
  visual coverage, weak public attributes; `legal_authority_notes`: reference GIS;
  `known_limitations`: terms and vector access unresolved.
- `candidate_layer_class`: `raster`; `candidate_loading_strategy`: tiles;
  `candidate_selection_kind`: none; `candidate_time_model`: snapshot;
  `provenance_kind`: official.
- `early_signal_value`: medium planning constraint; `implementation_priority`: `P0` for
  a visual pilot; `verification_status`: live declarations verified;
  `last_verified_at`: 2026-10-03.

### UPI-KGA-GP-INFRA — planned transport and social infrastructure

- `source_id`: `UPI-KGA-GP-INFRA`.
- `title`: General Plan 2023 infrastructure layers; `publisher`: KGA;
  `publisher_role`: planning authority.
- `official_status`: `OFFICIAL_GIS`; `source_family`: future transport/social/utility
  infrastructure.
- `primary_url`: [KGA map](https://portal.kgainfo.spb.ru/KGAMap/);
  `documentation_url`: [official General Plan page](https://www.gov.spb.ru/gov/otrasl/ingen/generalnyj-plan-sankt-peterburga/);
  `service_url`: [layer registry](https://portal.kgainfo.spb.ru/KGAMap/Map/GetLayers);
  `service_type`: proxied WMS; `format`: JSON/PNG.
- `access_mode`: public map; `authentication`: none observed; `license_or_terms`: unclear;
  `geometry_available`: yes; `geometry_type`: point/line/polygon;
  `crs`: EPSG:3857 rendering; `spatial_extent`: Saint Petersburg.
- `temporal_information`: General Plan horizon/product generation; `version_field`:
  `GP2023v2` layer prefix; `publication_date_field`: underlying act;
  `update_date_field`: blank; `status_field`: planned/existing semantics need layer-level
  validation; `object_identifier`: unknown; `document_identifier`: GP annex/layer ID.
- `historical_versions`: not exposed; `update_frequency_observed`: plan amendments;
  `update_frequency_claimed`: unknown; `automation_level`: `A` raster;
  `pagination_or_download_method`: WMS; `estimated_volume`: dozens of thematic layers;
  `change_suitability`: `SNAPSHOT_DIFF`/`DOCUMENT_EVENT`.
- `schema_notes`: verified streets, road structures, public-transport lines/stops,
  railways, transport facilities, schools, health, sport, social services and public
  spaces; `quality_notes`: meaning must be read from each annex;
  `legal_authority_notes`: GIS references the adopted plan; `known_limitations`: no
  feature attributes/stable IDs verified.
- `candidate_layer_class`: `raster`; `candidate_loading_strategy`: tiles;
  `candidate_selection_kind`: none; `candidate_time_model`: snapshot;
  `provenance_kind`: official.
- `early_signal_value`: medium `PLANNING`, not project commitment;
  `implementation_priority`: `P1`; `verification_status`: live declarations verified;
  `last_verified_at`: 2026-10-03.

### UPI-INFOECO-AIR — city environmental monitoring

- `source_id`: `UPI-INFOECO-AIR`.
- `title`: Environmental Portal of Saint Petersburg, atmospheric monitoring;
  `publisher`: Committee for Nature Use, Environmental Protection and Ecological Safety;
  `publisher_role`: city environmental monitoring authority.
- `official_status`: `OFFICIAL_INFORMATIONAL`; `source_family`: environment/air.
- `primary_url`: [Environmental Portal](https://www.infoeco.ru/);
  `documentation_url`: [official 2026 monitoring update](https://www.gov.spb.ru/press/governor/310139/);
  `service_url`: null; `service_type`: public portal; `format`: HTML/unknown.
- `access_mode`: intended public; `authentication`: unknown; `license_or_terms`: unknown;
  `geometry_available`: station locations likely displayed, not verified;
  `geometry_type`: point/unknown; `crs`: unknown; `spatial_extent`: Saint Petersburg.
- `temporal_information`: measurements and reporting periods; `version_field`: null;
  `publication_date_field`: reports; `update_date_field`: measurement time expected but
  endpoint not inspected; `status_field`: pollutant/quality values;
  `object_identifier`: station ID unknown; `document_identifier`: report ID/date.
- `historical_versions`: reports/measurements described, machine archive not verified;
  `update_frequency_observed`: official pages describe frequent measurements;
  `update_frequency_claimed`: monitoring is ongoing.
- `automation_level`: `F` at verification; `pagination_or_download_method`: unknown;
  `estimated_volume`: city network reported as 30 stations in 2026;
  `change_suitability`: `NOT_DIFFABLE` until endpoint discovery.
- `schema_notes`: no public schema obtained; `quality_notes`: official city source;
  `legal_authority_notes`: informational measurements; `known_limitations`: TLS request
  failed even in diagnostic mode and the software update was still referenced.
- `candidate_layer_class`: future `temporal-vector`; `candidate_loading_strategy`:
  independent; `candidate_selection_kind`: layer-feature; `candidate_time_model`: event;
  `provenance_kind`: official.
- `early_signal_value`: low for development, high for environmental context;
  `implementation_priority`: `P2`; `verification_status`: publisher claim verified,
  portal endpoint unavailable from environment; `last_verified_at`: 2026-10-03.

### UPI-HYDROMET-CLIMATE — official weather/climate observations

- `source_id`: `UPI-HYDROMET-CLIMATE`.
- `title`: Hydrometcentre / North-West UGMS Saint Petersburg climate and observations;
  `publisher`: Hydrometcentre of Russia and North-West UGMS;
  `publisher_role`: federal/state hydrometeorological organizations.
- `official_status`: `OFFICIAL_INFORMATIONAL`; `source_family`: wind/climate.
- `primary_url`: [Saint Petersburg observations](https://meteoinfo.ru/pogoda/russia/leningrad-region/sankt-peterburg);
  `documentation_url`: [Saint Petersburg climate normals](https://meteoinfo.ru/climate/klimatgorod/1726-1246618396);
  `service_url`: [North-West UGMS](https://www.meteo.nw.ru/);
  `service_type`: official web pages; `format`: HTML/tables.
- `access_mode`: public; `authentication`: none; `license_or_terms`: unknown.
- `geometry_available`: station coordinates appear on some climate pages, no GIS layer
  verified; `geometry_type`: point by derivation only; `crs`: WGS84-like coordinates,
  not formally specified; `spatial_extent`: station/city.
- `temporal_information`: current observations, archive links, 1961–1990 climate normals;
  `version_field`: averaging period; `publication_date_field`: page/report date;
  `update_date_field`: observation timestamp; `status_field`: null;
  `object_identifier`: station name/index where shown; `document_identifier`: null.
- `historical_versions`: observation archive is linked; complete machine access not
  tested; `update_frequency_observed`: subdaily current observations;
  `update_frequency_claimed`: operational.
- `automation_level`: `C`; `pagination_or_download_method`: HTML adapter/manual archive;
  `estimated_volume`: station time series; `change_suitability`: `DOCUMENT_EVENT` for
  reports, time-series append for observations.
- `schema_notes`: temperature, pressure, humidity, wind speed/direction and climate
  normals; `quality_notes`: official but not a citywide wind field;
  `legal_authority_notes`: measurement/reference, not planning regulation;
  `known_limitations`: no verified wind-rose dataset or stable API.
- `candidate_layer_class`: `temporal-vector` for stations or `derived-analysis` for an
  interpolated surface; `candidate_loading_strategy`: independent;
  `candidate_selection_kind`: layer-feature; `candidate_time_model`: event/range;
  `provenance_kind`: official for observations, derived for interpolation.
- `early_signal_value`: none for development; `implementation_priority`: `P2`;
  `verification_status`: official pages accessible; `last_verified_at`: 2026-10-03.

### UPI-KGA-SKYLINE — silhouette and protected-view constraints

- `source_id`: `UPI-KGA-SKYLINE`.
- `title`: PZZ silhouette-influence and historical-settlement layers;
  `publisher`: KGA; `publisher_role`: official planning GIS publisher.
- `official_status`: `OFFICIAL_GIS`; `source_family`: dominants/skyline.
- `primary_url`: [KGA map](https://portal.kgainfo.spb.ru/KGAMap/);
  `documentation_url`: [Law No. 820-7 publication context](https://www.gov.spb.ru/gov/otrasl/c_govcontrol/news/205207/);
  `service_url`: [layer registry](https://portal.kgainfo.spb.ru/KGAMap/Map/GetLayers);
  `service_type`: WMS layers including `PZZ_2025_P3_HIST_STT_SHAPE_INFL`;
  `format`: JSON/PNG.
- `access_mode`: public map; `authentication`: none observed; `license_or_terms`: unclear;
  `geometry_available`: official restriction geometry yes; `geometry_type`: polygon/line;
  `crs`: EPSG:3857 rendering; `spatial_extent`: Saint Petersburg.
- `temporal_information`: PZZ 2025 generation; `version_field`: layer generation;
  `publication_date_field`: underlying acts; `update_date_field`: blank;
  `status_field`: restriction class; `object_identifier`: unknown;
  `document_identifier`: underlying PZZ/heritage act.
- `historical_versions`: not exposed; `update_frequency_observed`: event-driven;
  `update_frequency_claimed`: unknown; `automation_level`: `A` raster;
  `pagination_or_download_method`: WMS; `estimated_volume`: unknown;
  `change_suitability`: `SNAPSHOT_DIFF`/`DOCUMENT_EVENT`.
- `schema_notes`: official silhouette-influence geometry exists; a complete named
  inventory for Saint Isaac's, Admiralty, Peter and Paul, Smolny and other dominants was
  not proven; `quality_notes`: constraint layer is not a viewshed;
  `legal_authority_notes`: cite underlying PZZ/heritage act;
  `known_limitations`: no public vector feature schema or official computed viewshed.
- `candidate_layer_class`: `raster` for official constraint; any viewshed must be
  `derived-analysis`; `candidate_loading_strategy`: tiles;
  `candidate_selection_kind`: none; `candidate_time_model`: snapshot;
  `provenance_kind`: official for constraint, derived for viewshed.
- `early_signal_value`: contextual only; `implementation_priority`: `P1` constraint,
  `P3` viewshed; `verification_status`: live declaration verified;
  `last_verified_at`: 2026-10-03.

### UPI-ESSK — Unified Construction Complex System

- `source_id`: `UPI-ESSK`.
- `title`: Unified Construction Complex System of Saint Petersburg (ESSK);
  `publisher`: Government of Saint Petersburg; `publisher_role`: official digital
  workflow portal connecting city authorities, subordinate organizations, utilities and
  developers.
- `official_status`: `OFFICIAL_REGISTER`; `source_family`: construction and urban-
  planning service workflows.
- `primary_url`: [ESSK portal](https://essk.gov.spb.ru/); `documentation_url`:
  [official city construction page](https://www.gov.spb.ru/helper/stroitelstvo/);
  `service_url`: null; `service_type`: authenticated workflow portal;
  `format`: browser application/unknown.
- `access_mode`: service workflows; `authentication`: electronic identity/signature is
  required for documented applicant workflows; `license_or_terms`: restricted/service
  terms.
- `geometry_available`: unknown; `geometry_type`: unknown; `crs`: unknown;
  `spatial_extent`: Saint Petersburg.
- `temporal_information`: application/workflow state expected but not publicly verified;
  `version_field`: unknown; `publication_date_field`: unknown; `update_date_field`:
  unknown; `status_field`: workflow-specific; `object_identifier`: unknown;
  `document_identifier`: application/permit identifiers expected but unverified.
- `historical_versions`: unknown; `update_frequency_observed`: unknown;
  `update_frequency_claimed`: operational since 2017 according to the city page;
  `automation_level`: `F`; `pagination_or_download_method`: authenticated/manual;
  `estimated_volume`: unknown; `change_suitability`: `NOT_DIFFABLE` without authorized
  access and an integration contract.
- `schema_notes`: no public API/schema established; `quality_notes`: official workflow
  system rather than an open dataset; `legal_authority_notes`: issued documents retain
  their own authority; `known_limitations`: endpoint failed TLS negotiation from the
  research environment and workflows are authenticated.
- `candidate_layer_class`: none directly; `candidate_loading_strategy`: external/manual;
  `candidate_selection_kind`: none; `candidate_time_model`: event if later authorized;
  `provenance_kind`: official.
- `early_signal_value`: potentially high `PLANNING`/`PERMIT`, but inaccessible for open
  automation; `implementation_priority`: `P3` pending an official integration route;
  `verification_status`: official role verified, endpoint unavailable;
  `last_verified_at`: 2026-10-03.

## Bounded probe baseline

| Source | Probe | Result | Payload / schema observation |
|---|---|---|---|
| KGA GIS | `GET /KGAMap/Map/GetLayers` | 200 JSON | 360,973 bytes; layer IDs, scales, access and export flags |
| KGA GIS | WMS `GetMap`, functional zones, 256×256 | 200 `image/png` | 18,092 bytes; valid PNG |
| KGA GIS | WMS `GetCapabilities` | 204 | capabilities document is not exposed through this proxy |
| TORIS | ArcGIS REST root `?f=pjson` | 200 JSON | 845 bytes; folders and services |
| Construction | MapServer metadata | 200 JSON | Query/Data; point/polygon layers and related permit tables |
| Construction | count-only queries | 200 JSON | 324 objects; 6,834 permit rows; 6,747 commissioning rows |
| GIS Torgi | public search, `size=1&page=0` | 200 JSON | 10,539 bytes; structured lot/status/date/category fields |
| RGIS | public map entry | 200 HTML after redirect | 1,187 bytes; public shell, cabinet auth is separate |
| NSPD | public map entry | 200 HTML | 12,928 bytes; no sanctioned API established |
| Open Data SPb | portal root | 404 HTML | official system page exists, live catalogue root unavailable |
| InfoEco | portal entry | TLS failure | no endpoint/schema claim made |
| ESSK | portal entry | TLS negotiation failure | official workflow role confirmed from city documentation; no public schema claim |

No probe downloaded a citywide dataset or mutated an external system. Several official
sites presented incomplete/self-signed certificate chains to the local client; diagnostic
`-k` was used only to establish public availability and is not an implementation plan.

## First official visual candidates

These are implementation-fit candidates, not an overall source ranking:

1. KGA General Plan functional zones — official, citywide, visually legible, proven WMS.
2. KGA PZZ territorial zones — official zoning context using the same proven transport.
3. KGA height/protection/flood constraints — visually meaningful, same bounded adapter.
4. TORIS construction objects — selectable structured features with stable IDs/statuses.
5. KGA KRT polygons — useful planning context, but only after legal/version labeling.

## Development-signal priority

| Stage | Best discovered source | Why |
|---|---|---|
| `EARLY_LAND` | GIS Torgi + KIO auction pages | Notice/lot identities, dates, status and cadastral/address evidence |
| `PLANNING` | DPT/PPT/PMT GIS + underlying acts | Planned boundaries precede permits; vector identifiers remain a gap |
| `DESIGN` | AGO GIS + requested ISOGD extract | Official decision evidence, but public attributes are incomplete |
| `PERMIT` | TORIS construction permit table | Machine-readable document IDs, dates, status and parent join |
| `CONSTRUCTION` | TORIS construction geometries/status | Stable object GUID/ROOTID and current status |
| `COMMISSIONING` | TORIS commissioning table | Structured official document rows joined to construction objects |
