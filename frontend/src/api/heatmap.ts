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

export type ScenarioDimension = {
  key: string;
  label: string;
  group: string;
  group_label: string;
  metric_key: string;
  display_order: number;
};

export type ScoreDistribution = {
  grid_version: string;
  scoring_signature: string;
  cell_count: number;
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
};

export type ScenarioExplanationTarget = {
  object_id: string;
  name: string | null;
  geometry_type: string;
  distance_m: number;
  area_m2: number | null;
};

export type ScenarioExplanationFactor = {
  metric_key: string;
  label: string;
  weight: number;
  individual_score: number;
  contribution: number;
  target: ScenarioExplanationTarget | null;
};

export type ScenarioExplanation = {
  grid_version: string;
  cell_id: string;
  scoring_signature: string;
  score: number;
  factors: ScenarioExplanationFactor[];
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

export const fetchScenarioDimensions = (signal?: AbortSignal): Promise<ScenarioDimension[]> =>
  apiJson<ScenarioDimension[]>(`${apiBaseUrl}/api/analysis/scenarios/dimensions`, {
    signal,
  });

export const fetchScoreDistribution = (
  request: { grid_version: string; weights: Record<string, number>; district_ids: string[] },
  signal?: AbortSignal,
): Promise<ScoreDistribution> =>
  apiJson<ScoreDistribution>(`${apiBaseUrl}/api/analysis/scoring/distribution`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });

export const fetchScenarioExplanation = (
  request: { cell_id: string; spec: string },
  signal?: AbortSignal,
): Promise<ScenarioExplanation> =>
  apiJson<ScenarioExplanation>(`${apiBaseUrl}/api/analysis/scenarios/explain`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
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
