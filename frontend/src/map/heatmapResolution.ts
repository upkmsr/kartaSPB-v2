export type HeatmapResolutionMode = "auto" | "200m" | "50m";

export const OVERVIEW_GRID_VERSION = "spb-square-200m-v1";
export const DETAIL_GRID_VERSION = "spb-square-50m-v1";
export const AUTO_DETAIL_MIN_ZOOM = 13;

export const resolveHeatmapGridVersion = (
  mode: HeatmapResolutionMode,
  zoom: number,
): string => {
  if (mode === "50m") return DETAIL_GRID_VERSION;
  if (mode === "200m") return OVERVIEW_GRID_VERSION;
  return zoom >= AUTO_DETAIL_MIN_ZOOM ? DETAIL_GRID_VERSION : OVERVIEW_GRID_VERSION;
};
