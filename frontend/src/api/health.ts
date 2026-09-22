export type ComponentStatus = {
  status: "ready" | "unavailable" | "outdated";
  detail: string | null;
};

export type ReadinessReport = {
  status: "ready" | "not_ready";
  database: ComponentStatus;
  postgis: ComponentStatus;
  migrations: ComponentStatus;
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

export async function fetchReadiness(signal?: AbortSignal): Promise<ReadinessReport> {
  const response = await fetch(`${apiBaseUrl}/api/health/ready`, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Readiness request failed with ${response.status}`);
  }
  return response.json() as Promise<ReadinessReport>;
}
