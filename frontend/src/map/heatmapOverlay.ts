import type { Map as MapLibreMap } from "maplibre-gl";
import type { PreparedHeatmap } from "../api/heatmap";

export const HEATMAP_SOURCE_ID = "analysis-heatmap-source";
export const HEATMAP_LAYER_ID = "analysis-heatmap-fill";
export const HEATMAP_MIN_ZOOM = 11;

type HeatmapOverlayMap = Pick<
  MapLibreMap,
  | "addLayer"
  | "addSource"
  | "getLayer"
  | "getSource"
  | "removeLayer"
  | "removeSource"
>;

const installedSignatures = new WeakMap<object, string>();

const removeInstalledOverlay = (map: HeatmapOverlayMap): void => {
  if (map.getLayer(HEATMAP_LAYER_ID)) map.removeLayer(HEATMAP_LAYER_ID);
  if (map.getSource(HEATMAP_SOURCE_ID)) map.removeSource(HEATMAP_SOURCE_ID);
  installedSignatures.delete(map as object);
};

export const updateHeatmapOverlay = (
  map: HeatmapOverlayMap,
  heatmap: PreparedHeatmap | null,
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
        "fill-color": [
          "interpolate",
          ["linear"],
          ["get", "score"],
          0,
          "#d73027",
          25,
          "#fc8d59",
          50,
          "#fee08b",
          75,
          "#91cf60",
          100,
          "#1a9850",
        ],
        "fill-opacity": 0.72,
      },
    },
    beforeId && map.getLayer(beforeId) ? beforeId : undefined,
  );
  installedSignatures.set(map as object, heatmap.scoring_signature);
};
