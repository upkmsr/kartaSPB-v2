import type { GeoJSONSource, Map as MapLibreMap } from "maplibre-gl";
import type { DistrictGeometryFeatureCollection } from "../api/districts";

export const SELECTED_DISTRICT_SOURCE_ID = "selected-districts";
export const SELECTED_DISTRICT_FILL_LAYER_ID = "selected-district-fill";
export const SELECTED_DISTRICT_OUTLINE_LAYER_ID = "selected-district-outline";

type DistrictOverlayMap = Pick<
  MapLibreMap,
  "addLayer" | "addSource" | "getLayer" | "getSource"
>;

export const installSelectedDistrictOverlay = (
  map: DistrictOverlayMap,
  data: DistrictGeometryFeatureCollection,
  fillBeforeId?: string,
  outlineBeforeId?: string,
): void => {
  if (!map.getSource(SELECTED_DISTRICT_SOURCE_ID)) {
    map.addSource(SELECTED_DISTRICT_SOURCE_ID, { type: "geojson", data });
  }
  if (!map.getLayer(SELECTED_DISTRICT_FILL_LAYER_ID)) {
    map.addLayer(
      {
        id: SELECTED_DISTRICT_FILL_LAYER_ID,
        source: SELECTED_DISTRICT_SOURCE_ID,
        type: "fill",
        paint: {
          "fill-color": "#38e8c6",
          "fill-opacity": 0.08,
        },
      },
      fillBeforeId && map.getLayer(fillBeforeId) ? fillBeforeId : undefined,
    );
  }
  if (!map.getLayer(SELECTED_DISTRICT_OUTLINE_LAYER_ID)) {
    map.addLayer(
      {
        id: SELECTED_DISTRICT_OUTLINE_LAYER_ID,
        source: SELECTED_DISTRICT_SOURCE_ID,
        type: "line",
        paint: {
          "line-color": "#38e8c6",
          "line-opacity": 0.96,
          "line-width": ["interpolate", ["linear"], ["zoom"], 7, 3, 10, 2.5, 14, 1.8, 18, 1.4],
        },
      },
      outlineBeforeId && map.getLayer(outlineBeforeId) ? outlineBeforeId : undefined,
    );
  }
};

export const setSelectedDistrictOverlayData = (
  map: Pick<MapLibreMap, "getSource">,
  data: DistrictGeometryFeatureCollection,
): void => {
  const source = map.getSource(SELECTED_DISTRICT_SOURCE_ID) as GeoJSONSource | undefined;
  source?.setData(data as Parameters<GeoJSONSource["setData"]>[0]);
};
