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
