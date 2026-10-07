export type NormalizationPoint = {
  raw_value: number;
  score: number;
};

export type NormalizationProfile = {
  metric_key: string;
  normalization_version: string;
  label: string;
  method: string;
  points: NormalizationPoint[];
  checksum: string;
};

export type HeatmapPrepareRequest = {
  grid_version?: string;
  weights: Record<string, number>;
};

export type PreparedHeatmap = {
  grid_version: string;
  weights: Record<string, number>;
  scoring_signature: string;
  spec: string;
  cell_count: number;
  min: number;
  max: number;
  mean: number;
  tile_url_template: string;
  delivery_version: string;
};

export class HeatmapApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "HeatmapApiError";
  }
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

const apiJson = async <T>(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<T> => {
  const response = await fetch(input, {
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });
  if (!response.ok) {
    let message = `Heatmap API request failed (${response.status})`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) message = payload.detail;
    } catch {
      // Preserve the stable fallback when an upstream response is not JSON.
    }
    throw new HeatmapApiError(message, response.status);
  }
  return (await response.json()) as T;
};

export const fetchNormalizationProfiles = (
  signal?: AbortSignal,
): Promise<NormalizationProfile[]> =>
  apiJson<NormalizationProfile[]>(`${apiBaseUrl}/api/analysis/scoring/normalizations`, {
    signal,
  });

export const prepareHeatmap = async (
  request: HeatmapPrepareRequest,
  signal?: AbortSignal,
): Promise<PreparedHeatmap> => {
  const prepared = await apiJson<PreparedHeatmap>(
    `${apiBaseUrl}/api/analysis/heatmap/prepare`,
    {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
    },
  );
  return {
    ...prepared,
    tile_url_template:
      apiBaseUrl && prepared.tile_url_template.startsWith("/")
        ? `${apiBaseUrl}${prepared.tile_url_template}`
        : prepared.tile_url_template,
  };
};
