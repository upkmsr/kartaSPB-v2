import type { ExpressionSpecification, Map as MapLibreMap } from "maplibre-gl";
import type { PreparedHeatmap } from "../api/heatmap";

export const HEATMAP_SOURCE_ID = "analysis-heatmap-source";
export const HEATMAP_LAYER_ID = "analysis-heatmap-fill";
export const HEATMAP_MIN_ZOOM = 11;
export const HEATMAP_COLORS = [
  "#d73027",
  "#fc8d59",
  "#fee08b",
  "#91cf60",
  "#1a9850",
] as const;

export type HeatmapDisplayRange = {
  min: number;
  max: number;
};

export const DEFAULT_HEATMAP_DISPLAY_RANGE: HeatmapDisplayRange = {
  min: 40,
  max: 100,
};

type HeatmapOverlayMap = Pick<
  MapLibreMap,
  | "addLayer"
  | "addSource"
  | "getLayer"
  | "getSource"
  | "removeLayer"
  | "removeSource"
  | "setPaintProperty"
>;

const installedSignatures = new WeakMap<object, string>();
const installedDisplayRanges = new WeakMap<object, string>();

const rangeKey = (range: HeatmapDisplayRange): string => `${range.min}:${range.max}`;

export const heatmapLegendValues = (
  range: HeatmapDisplayRange,
): [number, number, number, number, number] => {
  if (
    !Number.isFinite(range.min) ||
    !Number.isFinite(range.max) ||
    range.min < 0 ||
    range.max > 100 ||
    range.min >= range.max
  ) {
    throw new Error("Heatmap display range must satisfy 0 <= min < max <= 100");
  }
  const step = (range.max - range.min) / 4;
  return [
    range.min,
    range.min + step,
    range.min + step * 2,
    range.min + step * 3,
    range.max,
  ];
};

export const heatmapColorExpression = (
  range: HeatmapDisplayRange,
): ExpressionSpecification => {
  const values = heatmapLegendValues(range);
  return [
    "interpolate",
    ["linear"],
    ["get", "score"],
    values[0],
    HEATMAP_COLORS[0],
    values[1],
    HEATMAP_COLORS[1],
    values[2],
    HEATMAP_COLORS[2],
    values[3],
    HEATMAP_COLORS[3],
    values[4],
    HEATMAP_COLORS[4],
  ];
};

const removeInstalledOverlay = (map: HeatmapOverlayMap): void => {
  if (map.getLayer(HEATMAP_LAYER_ID)) map.removeLayer(HEATMAP_LAYER_ID);
  if (map.getSource(HEATMAP_SOURCE_ID)) map.removeSource(HEATMAP_SOURCE_ID);
  installedSignatures.delete(map as object);
  installedDisplayRanges.delete(map as object);
};

export const updateHeatmapOverlay = (
  map: HeatmapOverlayMap,
  heatmap: PreparedHeatmap | null,
  displayRange: HeatmapDisplayRange = DEFAULT_HEATMAP_DISPLAY_RANGE,
  beforeId?: string,
): void => {
  if (heatmap === null) {
    removeInstalledOverlay(map);
    return;
  }
  const sourceExists = Boolean(map.getSource(HEATMAP_SOURCE_ID));
  const layerExists = Boolean(map.getLayer(HEATMAP_LAYER_ID));
  if (
    sourceExists &&
    layerExists &&
    installedSignatures.get(map as object) === heatmap.scoring_signature
  ) {
    if (installedDisplayRanges.get(map as object) !== rangeKey(displayRange)) {
      map.setPaintProperty(
        HEATMAP_LAYER_ID,
        "fill-color",
        heatmapColorExpression(displayRange),
      );
      installedDisplayRanges.set(map as object, rangeKey(displayRange));
    }
    return;
  }
  removeInstalledOverlay(map);
  map.addSource(HEATMAP_SOURCE_ID, {
    type: "vector",
    tiles: [heatmap.tile_url_template],
    minzoom: HEATMAP_MIN_ZOOM,
    maxzoom: 22,
  });
  map.addLayer(
    {
      id: HEATMAP_LAYER_ID,
      source: HEATMAP_SOURCE_ID,
      "source-layer": "analysis_heatmap",
      type: "fill",
      minzoom: HEATMAP_MIN_ZOOM,
      paint: {
        "fill-color": heatmapColorExpression(displayRange),
        "fill-opacity": 0.72,
      },
    },
    beforeId && map.getLayer(beforeId) ? beforeId : undefined,
  );
  installedSignatures.set(map as object, heatmap.scoring_signature);
  installedDisplayRanges.set(map as object, rangeKey(displayRange));
};
