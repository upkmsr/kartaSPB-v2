export type InfluenceChannel = {
  metric_key: string;
  score_run_id: string;
  property_name: string;
};

export type PreparedInfluence = {
  grid_version: string;
  influence_signature: string;
  spec: string;
  cell_count: number;
  channels: InfluenceChannel[];
  tile_url_template: string;
  delivery_version: "influence-mvt-v1";
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

export const prepareInfluence = async (
  request: { grid_version: string; metric_keys: string[] },
  signal?: AbortSignal,
): Promise<PreparedInfluence> => {
  const response = await fetch(`${apiBaseUrl}/api/analysis/influence/prepare`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });
  if (!response.ok) throw new Error(`Influence API request failed (${response.status})`);
  const prepared = (await response.json()) as PreparedInfluence;
  return {
    ...prepared,
    tile_url_template:
      apiBaseUrl && prepared.tile_url_template.startsWith("/")
        ? `${apiBaseUrl}${prepared.tile_url_template}`
        : prepared.tile_url_template,
  };
};
