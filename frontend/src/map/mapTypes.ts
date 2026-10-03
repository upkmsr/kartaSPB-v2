import type {
  Feature,
  FeatureCollection,
  LineString,
  MultiLineString,
  MultiPoint,
  MultiPolygon,
  Point,
  Polygon,
} from "geojson";

export type GeoJSONGeometry =
  | Point
  | MultiPoint
  | LineString
  | MultiLineString
  | Polygon
  | MultiPolygon;

export type MapFeatureProperties = {
  canonical_id: string;
  facility_entity_id?: string | null;
  representative_canonical_id?: string;
  display_canonical_id?: string;
  member_canonical_ids?: string[];
  name: string | null;
  categories: string[];
  object_kind: string;
};

export type CatalogFeature = Feature<GeoJSONGeometry, MapFeatureProperties> & {
  id: string;
};

export type CatalogFeatureCollection = FeatureCollection<GeoJSONGeometry, MapFeatureProperties> & {
  features: CatalogFeature[];
};

export type SourceSummary = {
  provider: string;
  object_type: string;
  object_id: string;
  source_version: string | null;
  geometry_quality: string;
};

export type ObjectDetail = {
  id: string;
  name: string | null;
  categories: string[];
  object_kind: string;
  geometry_type: string;
  properties: Record<string, unknown>;
  sources: SourceSummary[];
  facility?: FacilityRepresentation | null;
};

export type FacilityMember = {
  canonical_id: string;
  geometry_role: string;
  source_type: string;
  source_object_id: string;
};

export type FacilityRepresentation = {
  id: string;
  category_key: string;
  representative_object_id: string;
  display_object_id: string;
  analysis_object_id: string;
  members: FacilityMember[];
};

export type MapBounds = {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
};

export type MapNavigationTarget =
  | { kind: "bbox"; bbox: [number, number, number, number] }
  | { kind: "point"; center: [number, number]; zoom: number };

export type MapNavigationRequest = MapNavigationTarget & { sequence: number };

export type MapRequestState =
  | { status: "idle" }
  | { status: "pending-manual-load"; loadableLayerIds: string[] }
  | { status: "loading"; loadableLayerIds: string[] }
  | { status: "ready"; featureCount: number; durationMs: number; loadedLayerIds: string[] }
  | { status: "empty"; durationMs: number; loadedLayerIds: string[] }
  | { status: "no-enabled-layers" }
  | { status: "waiting-for-zoom"; waitingLayerIds: string[] }
  | { status: "bbox-too-large" }
  | { status: "feature-limit" }
  | { status: "stale-error"; message: string }
  | { status: "error"; message: string };

export type ObjectCardState =
  | { status: "closed" }
  | { status: "loading"; objectId: string }
  | { status: "loaded"; detail: ObjectDetail }
  | { status: "not-found"; objectId: string }
  | { status: "error"; objectId: string };

export const EMPTY_FEATURE_COLLECTION: CatalogFeatureCollection = {
  type: "FeatureCollection",
  features: [],
};
