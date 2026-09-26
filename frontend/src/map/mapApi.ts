import {
  EMPTY_FEATURE_COLLECTION,
  type CatalogFeature,
  type CatalogFeatureCollection,
  type MapBounds,
  type MapFeatureProperties,
  type ObjectDetail,
} from "./mapTypes";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

const MAX_LONGITUDE_SPAN = 0.5;
const MAX_LATITUDE_SPAN = 0.3;
const MAX_BBOX_AREA = 0.1;

export type MapFeatureRequest = {
  bounds: MapBounds;
  categories: string[];
  districtIds?: string[];
  limit?: number;
};

export type BboxGuardResult =
  | { valid: true; bbox: string }
  | { valid: false; reason: "coordinates" | "order" | "span" | "area" };

export class MapApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message);
  }
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const isStringArray = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((item) => typeof item === "string");

const isMapFeatureProperties = (value: unknown): value is MapFeatureProperties =>
  isRecord(value) &&
  typeof value.canonical_id === "string" &&
  (typeof value.name === "string" || value.name === null) &&
  isStringArray(value.categories) &&
  typeof value.object_kind === "string";

const supportedGeometryTypes = new Set([
  "Point",
  "MultiPoint",
  "LineString",
  "MultiLineString",
  "Polygon",
  "MultiPolygon",
]);

const isCatalogFeature = (value: unknown): value is CatalogFeature => {
  if (!isRecord(value) || value.type !== "Feature" || typeof value.id !== "string") {
    return false;
  }
  if (
    !isRecord(value.geometry) ||
    typeof value.geometry.type !== "string" ||
    !supportedGeometryTypes.has(value.geometry.type)
  ) {
    return false;
  }
  return Array.isArray(value.geometry.coordinates) && isMapFeatureProperties(value.properties);
};

export const isCatalogFeatureCollection = (value: unknown): value is CatalogFeatureCollection =>
  isRecord(value) &&
  value.type === "FeatureCollection" &&
  Array.isArray(value.features) &&
  value.features.every(isCatalogFeature);

const isObjectDetail = (value: unknown): value is ObjectDetail =>
  isRecord(value) &&
  typeof value.id === "string" &&
  (typeof value.name === "string" || value.name === null) &&
  isStringArray(value.categories) &&
  typeof value.object_kind === "string" &&
  typeof value.geometry_type === "string" &&
  isRecord(value.properties) &&
  Array.isArray(value.sources) &&
  value.sources.every(
    (source) =>
      isRecord(source) &&
      typeof source.provider === "string" &&
      typeof source.object_type === "string" &&
      typeof source.object_id === "string" &&
      (typeof source.source_version === "string" || source.source_version === null) &&
      typeof source.geometry_quality === "string",
  );

export const guardBbox = (bounds: MapBounds): BboxGuardResult => {
  const coordinates = [bounds.minLon, bounds.minLat, bounds.maxLon, bounds.maxLat];
  if (
    !coordinates.every(Number.isFinite) ||
    bounds.minLon < -180 ||
    bounds.maxLon > 180 ||
    bounds.minLat < -90 ||
    bounds.maxLat > 90
  ) {
    return { valid: false, reason: "coordinates" };
  }
  if (bounds.minLon >= bounds.maxLon || bounds.minLat >= bounds.maxLat) {
    return { valid: false, reason: "order" };
  }
  const longitudeSpan = bounds.maxLon - bounds.minLon;
  const latitudeSpan = bounds.maxLat - bounds.minLat;
  if (longitudeSpan > MAX_LONGITUDE_SPAN || latitudeSpan > MAX_LATITUDE_SPAN) {
    return { valid: false, reason: "span" };
  }
  if (longitudeSpan * latitudeSpan > MAX_BBOX_AREA) {
    return { valid: false, reason: "area" };
  }
  return { valid: true, bbox: coordinates.join(",") };
};

export const buildMapFeaturesUrl = ({
  bounds,
  categories,
  districtIds = [],
  limit = 5000,
}: MapFeatureRequest): string => {
  const guard = guardBbox(bounds);
  if (!guard.valid) {
    throw new Error(`Cannot build map request for invalid bbox: ${guard.reason}`);
  }
  const params = new URLSearchParams({
    bbox: guard.bbox,
    categories: categories.join(","),
    limit: String(limit),
  });
  if (districtIds.length > 0) params.set("districts", districtIds.join(","));
  return `${apiBaseUrl}/api/map/features?${params.toString()}`;
};

const responseError = async (response: Response): Promise<MapApiError> => {
  let code: string | undefined;
  let message = `Map API request failed with ${response.status}`;
  try {
    const body: unknown = await response.json();
    if (isRecord(body) && isRecord(body.detail)) {
      if (typeof body.detail.code === "string") code = body.detail.code;
      if (typeof body.detail.message === "string") message = body.detail.message;
    }
  } catch {
    // A non-JSON upstream error is still represented by status and a safe message.
  }
  return new MapApiError(message, response.status, code);
};

export const fetchMapFeatures = async (
  request: MapFeatureRequest,
  signal?: AbortSignal,
): Promise<CatalogFeatureCollection> => {
  if (request.categories.length === 0) return EMPTY_FEATURE_COLLECTION;
  const response = await fetch(buildMapFeaturesUrl(request), {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw await responseError(response);
  const payload: unknown = await response.json();
  if (!isCatalogFeatureCollection(payload)) {
    throw new MapApiError("Map API returned an invalid GeoJSON response", response.status);
  }
  return payload;
};

export const fetchObjectDetail = async (
  objectId: string,
  signal?: AbortSignal,
): Promise<ObjectDetail> => {
  const requestUrl = `${apiBaseUrl}/api/objects/${encodeURIComponent(objectId)}`;
  const response = await fetch(requestUrl, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw await responseError(response);
  const payload: unknown = await response.json();
  if (!isObjectDetail(payload)) {
    throw new MapApiError("Object API returned an invalid response", response.status);
  }
  return payload;
};

type MapFeatureFetcher = (
  request: MapFeatureRequest,
  signal?: AbortSignal,
) => Promise<CatalogFeatureCollection>;

export class LatestMapRequest {
  private sequence = 0;
  private controller: AbortController | null = null;

  constructor(private readonly fetcher: MapFeatureFetcher = fetchMapFeatures) {}

  cancel(): void {
    this.sequence += 1;
    this.controller?.abort();
    this.controller = null;
  }

  async run(
    request: MapFeatureRequest,
    onSuccess: (collection: CatalogFeatureCollection) => void,
    onError: (error: unknown) => void,
  ): Promise<void> {
    this.controller?.abort();
    const controller = new AbortController();
    this.controller = controller;
    const requestSequence = ++this.sequence;
    try {
      const collection = await this.fetcher(request, controller.signal);
      if (requestSequence === this.sequence && !controller.signal.aborted) {
        onSuccess(collection);
      }
    } catch (error) {
      if (requestSequence === this.sequence && !controller.signal.aborted) {
        onError(error);
      }
    }
  }
}
