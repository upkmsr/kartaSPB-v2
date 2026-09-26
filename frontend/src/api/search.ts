import type { Point } from "geojson";

export const MIN_SEARCH_QUERY_LENGTH = 3;
export const MAX_SEARCH_QUERY_LENGTH = 100;
export const SEARCH_DEBOUNCE_MS = 250;

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

export type SearchBbox = [number, number, number, number];

export type SearchResult = {
  id: string;
  name: string;
  categories: string[];
  object_kind: string;
  geometry_type: string;
  representative_point: Point;
  bbox: SearchBbox;
};

export type SearchResponse = {
  type: "SearchResults";
  results: SearchResult[];
};

export type SearchRequest = {
  query: string;
  categoryKeys?: readonly string[];
  districtIds?: readonly string[];
  limit?: number;
};

export class SearchApiError extends Error {
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

const isPoint = (value: unknown): value is Point =>
  isRecord(value) &&
  value.type === "Point" &&
  Array.isArray(value.coordinates) &&
  value.coordinates.length === 2 &&
  value.coordinates.every(Number.isFinite);

const isBbox = (value: unknown): value is SearchBbox =>
  Array.isArray(value) && value.length === 4 && value.every(Number.isFinite);

const isSearchResult = (value: unknown): value is SearchResult =>
  isRecord(value) &&
  typeof value.id === "string" &&
  typeof value.name === "string" &&
  isStringArray(value.categories) &&
  typeof value.object_kind === "string" &&
  typeof value.geometry_type === "string" &&
  isPoint(value.representative_point) &&
  isBbox(value.bbox);

const isSearchResponse = (value: unknown): value is SearchResponse =>
  isRecord(value) &&
  value.type === "SearchResults" &&
  Array.isArray(value.results) &&
  value.results.every(isSearchResult);

export const normalizeSearchQuery = (query: string): string =>
  query.trim().toLocaleLowerCase("ru-RU").replaceAll("ё", "е").replace(/\s+/g, " ");

export const buildSearchUrl = ({
  query,
  categoryKeys = [],
  districtIds = [],
  limit = 20,
}: SearchRequest): string => {
  const normalizedQuery = normalizeSearchQuery(query);
  if (
    normalizedQuery.length < MIN_SEARCH_QUERY_LENGTH ||
    normalizedQuery.length > MAX_SEARCH_QUERY_LENGTH
  ) {
    throw new Error("Search query must contain 3-100 normalized characters");
  }
  const params = new URLSearchParams({ q: normalizedQuery, limit: String(limit) });
  if (categoryKeys.length > 0) params.set("categories", categoryKeys.join(","));
  if (districtIds.length > 0) params.set("districts", districtIds.join(","));
  return `${apiBaseUrl}/api/search?${params.toString()}`;
};

const responseError = async (response: Response): Promise<SearchApiError> => {
  let code: string | undefined;
  let message = `Search API request failed with ${response.status}`;
  try {
    const body: unknown = await response.json();
    if (isRecord(body) && isRecord(body.detail)) {
      if (typeof body.detail.code === "string") code = body.detail.code;
      if (typeof body.detail.message === "string") message = body.detail.message;
    }
  } catch {
    // Non-JSON upstream failures still become a safe recoverable search error.
  }
  return new SearchApiError(message, response.status, code);
};

export const fetchSearchResults = async (
  request: SearchRequest,
  signal?: AbortSignal,
): Promise<SearchResult[]> => {
  const response = await fetch(buildSearchUrl(request), {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw await responseError(response);
  const payload: unknown = await response.json();
  if (!isSearchResponse(payload)) {
    throw new SearchApiError("Search API returned an invalid response", response.status);
  }
  return payload.results;
};

type SearchFetcher = typeof fetchSearchResults;

export class LatestSearchRequest {
  private controller: AbortController | null = null;
  private sequence = 0;

  constructor(private readonly fetcher: SearchFetcher = fetchSearchResults) {}

  cancel(): void {
    this.sequence += 1;
    this.controller?.abort();
    this.controller = null;
  }

  async run(
    request: SearchRequest,
    onSuccess: (results: SearchResult[]) => void,
    onError: (error: unknown) => void,
  ): Promise<void> {
    this.controller?.abort();
    const controller = new AbortController();
    const sequence = ++this.sequence;
    this.controller = controller;
    try {
      const results = await this.fetcher(request, controller.signal);
      if (sequence === this.sequence && !controller.signal.aborted) onSuccess(results);
    } catch (error) {
      if (sequence === this.sequence && !controller.signal.aborted) onError(error);
    } finally {
      if (sequence === this.sequence) this.controller = null;
    }
  }
}
