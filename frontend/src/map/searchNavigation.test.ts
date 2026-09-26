import { describe, expect, it } from "vitest";
import type { SearchResult } from "../api/search";
import { searchResultNavigation } from "./searchNavigation";

const searchResult = (geometryType: string, bbox: SearchResult["bbox"]): SearchResult => ({
  id: `id-${geometryType}`,
  name: geometryType,
  categories: ["nature.park"],
  object_kind: "feature",
  geometry_type: geometryType,
  representative_point: { type: "Point", coordinates: [30.31, 59.94] },
  bbox,
});

describe("search result navigation", () => {
  it("uses flyTo for Point results", () => {
    expect(searchResultNavigation(searchResult("Point", [30.31, 59.94, 30.31, 59.94]))).toEqual({
      kind: "point",
      center: [30.31, 59.94],
      zoom: 16,
    });
  });

  it.each(["LineString", "Polygon", "MultiPolygon"])(
    "uses fitBounds for %s results",
    (geometryType) => {
      expect(
        searchResultNavigation(searchResult(geometryType, [30.2, 59.8, 30.4, 60])),
      ).toEqual({ kind: "bbox", bbox: [30.2, 59.8, 30.4, 60] });
    },
  );

  it("falls back to the representative point for a degenerate bbox", () => {
    expect(
      searchResultNavigation(searchResult("LineString", [30.31, 59.94, 30.31, 59.94])),
    ).toEqual({ kind: "point", center: [30.31, 59.94], zoom: 16 });
  });
});
