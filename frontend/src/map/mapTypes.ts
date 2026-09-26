import type { CircleLayerSpecification, FillLayerSpecification, LineLayerSpecification } from "maplibre-gl";
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
};

export type RenderGeometry = "point" | "line" | "polygon";

export type RenderDefinition =
  | {
      id: string;
      order: number;
      type: "circle";
      geometry: "point";
      paint: NonNullable<CircleLayerSpecification["paint"]>;
    }
  | {
      id: string;
      order: number;
      type: "line";
      geometry: "line" | "polygon";
      paint: NonNullable<LineLayerSpecification["paint"]>;
    }
  | {
      id: string;
      order: number;
      type: "fill";
      geometry: "polygon";
      paint: NonNullable<FillLayerSpecification["paint"]>;
    };

export type LogicalLayer = {
  id: string;
  categoryKey: string;
  label: string;
  defaultVisible: boolean;
  minZoom: number;
  interactive: boolean;
  renderDefinitions: RenderDefinition[];
};

export type MapBounds = {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
};

export type MapNavigationRequest = {
  sequence: number;
  bbox: [number, number, number, number];
};

export type MapRequestState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; featureCount: number; durationMs: number }
  | { status: "empty"; durationMs: number }
  | { status: "bbox-too-large" }
  | { status: "feature-limit" }
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
