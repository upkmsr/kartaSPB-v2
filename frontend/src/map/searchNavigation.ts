import type { SearchResult } from "../api/search";
import type { MapNavigationTarget } from "./mapTypes";

const hasUsefulBbox = ([minLon, minLat, maxLon, maxLat]: SearchResult["bbox"]): boolean =>
  minLon < maxLon && minLat < maxLat;

export const searchResultNavigation = (result: SearchResult): MapNavigationTarget => {
  if (result.geometry_type !== "Point" && hasUsefulBbox(result.bbox)) {
    return { kind: "bbox", bbox: result.bbox };
  }
  return {
    kind: "point",
    center: [result.representative_point.coordinates[0], result.representative_point.coordinates[1]],
    zoom: 16,
  };
};
