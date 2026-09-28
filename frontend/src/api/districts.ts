import type { Feature, FeatureCollection, MultiPolygon, Polygon } from "geojson";

export type DistrictBbox = [number, number, number, number];

export type District = {
  id: string;
  name: string;
  slug: string;
  display_order: number;
  bbox: DistrictBbox;
};

export type DistrictListResponse = {
  districts: District[];
};

export type DistrictGeometryProperties = {
  id: string;
  name: string;
  slug: string;
};

export type DistrictGeometryFeature = Feature<
  Polygon | MultiPolygon,
  DistrictGeometryProperties
> & { id: string };

export type DistrictGeometryFeatureCollection = FeatureCollection<
  Polygon | MultiPolygon,
  DistrictGeometryProperties
> & { features: DistrictGeometryFeature[] };

export const EMPTY_DISTRICT_GEOMETRY: DistrictGeometryFeatureCollection = {
  type: "FeatureCollection",
  features: [],
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const isDistrictBbox = (value: unknown): value is DistrictBbox =>
  Array.isArray(value) && value.length === 4 && value.every(Number.isFinite);

const isDistrict = (value: unknown): value is District =>
  isRecord(value) &&
  typeof value.id === "string" &&
  typeof value.name === "string" &&
  typeof value.slug === "string" &&
  typeof value.display_order === "number" &&
  isDistrictBbox(value.bbox);

const isDistrictListResponse = (value: unknown): value is DistrictListResponse =>
  isRecord(value) && Array.isArray(value.districts) && value.districts.every(isDistrict);

const isDistrictGeometryFeature = (value: unknown): value is DistrictGeometryFeature =>
  isRecord(value) &&
  value.type === "Feature" &&
  typeof value.id === "string" &&
  isRecord(value.properties) &&
  value.properties.id === value.id &&
  typeof value.properties.name === "string" &&
  typeof value.properties.slug === "string" &&
  isRecord(value.geometry) &&
  (value.geometry.type === "Polygon" || value.geometry.type === "MultiPolygon") &&
  Array.isArray(value.geometry.coordinates);

const isDistrictGeometryFeatureCollection = (
  value: unknown,
): value is DistrictGeometryFeatureCollection =>
  isRecord(value) &&
  value.type === "FeatureCollection" &&
  Array.isArray(value.features) &&
  value.features.every(isDistrictGeometryFeature);

export async function fetchDistricts(signal?: AbortSignal): Promise<District[]> {
  const response = await fetch(`${apiBaseUrl}/api/districts`, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`District API request failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isDistrictListResponse(payload)) {
    throw new Error("District API returned an invalid response");
  }
  return [...payload.districts].sort(
    (left, right) => left.display_order - right.display_order,
  );
}

export async function fetchDistrictGeometry(
  districtIds: readonly string[],
  signal?: AbortSignal,
): Promise<DistrictGeometryFeatureCollection> {
  if (districtIds.length === 0) return EMPTY_DISTRICT_GEOMETRY;
  const params = new URLSearchParams({ districts: districtIds.join(",") });
  const response = await fetch(`${apiBaseUrl}/api/districts/geometry?${params.toString()}`, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`District geometry API request failed with ${response.status}`);
  }
  const payload: unknown = await response.json();
  if (!isDistrictGeometryFeatureCollection(payload)) {
    throw new Error("District geometry API returned an invalid response");
  }
  return payload;
}

type DistrictGeometryFetcher = (
  districtIds: readonly string[],
  signal?: AbortSignal,
) => Promise<DistrictGeometryFeatureCollection>;

export class LatestDistrictGeometryRequest {
  private sequence = 0;
  private controller: AbortController | null = null;

  constructor(private readonly fetcher: DistrictGeometryFetcher = fetchDistrictGeometry) {}

  cancel(): void {
    this.sequence += 1;
    this.controller?.abort();
    this.controller = null;
  }

  async run(
    districtIds: readonly string[],
    onSuccess: (collection: DistrictGeometryFeatureCollection) => void,
    onError: (error: unknown) => void,
  ): Promise<void> {
    this.controller?.abort();
    const controller = new AbortController();
    this.controller = controller;
    const requestSequence = ++this.sequence;
    try {
      const collection = await this.fetcher(districtIds, controller.signal);
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

export function combinedDistrictBbox(districts: readonly District[]): DistrictBbox | null {
  if (districts.length === 0) return null;
  return districts.reduce<DistrictBbox>(
    (combined, district) => [
      Math.min(combined[0], district.bbox[0]),
      Math.min(combined[1], district.bbox[1]),
      Math.max(combined[2], district.bbox[2]),
      Math.max(combined[3], district.bbox[3]),
    ],
    [...districts[0].bbox],
  );
}
