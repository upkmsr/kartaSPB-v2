import type {
  FilterSpecification,
  StyleSpecification,
  SymbolLayerSpecification,
} from "maplibre-gl";
import { describe, expect, it, vi } from "vitest";
import { alignOpenFreeMapRoadArrows } from "./basemapStyle";

const arrowLayer = (
  id: string,
  oneway: 1 | -1,
  rotation: number,
): SymbolLayerSpecification => ({
  id,
  type: "symbol" as const,
  source: "openmaptiles",
  "source-layer": "transportation",
  filter: ["==", ["get", "oneway"], oneway] as FilterSpecification,
  layout: {
    "symbol-placement": "line" as const,
    "symbol-spacing": 200,
    "icon-image": "oneway",
    "icon-rotate": rotation,
    "icon-rotation-alignment": "map" as const,
  },
});

const style = (layers: StyleSpecification["layers"]): StyleSpecification => ({
  version: 8,
  sources: { openmaptiles: { type: "vector", url: "https://tiles.openfreemap.org/planet" } },
  layers,
});

describe("OpenFreeMap road direction arrows", () => {
  it("rotates the upward sprite onto the line axis while preserving forward/reverse semantics", () => {
    const setLayoutProperty = vi.fn();
    const map = {
      getStyle: () =>
        style([
          arrowLayer("road_oneway", 1, 0),
          arrowLayer("road_oneway_opposite", -1, 180),
          {
            id: "road-label",
            type: "symbol",
            source: "openmaptiles",
            "source-layer": "transportation_name",
            layout: { "text-field": ["get", "name"] },
          },
        ]),
      setLayoutProperty,
    };

    alignOpenFreeMapRoadArrows(map as never);

    expect(setLayoutProperty.mock.calls).toEqual([
      ["road_oneway", "icon-rotate", 90],
      ["road_oneway_opposite", "icon-rotate", 270],
    ]);
  });

  it("does not alter similarly named layers outside the exact OpenFreeMap contract", () => {
    const setLayoutProperty = vi.fn();
    const map = {
      getStyle: () =>
        style([
          { ...arrowLayer("road_oneway", 1, 0), source: "custom" },
          { ...arrowLayer("road_oneway_opposite", -1, 45) },
        ]),
      setLayoutProperty,
    };

    alignOpenFreeMapRoadArrows(map as never);

    expect(setLayoutProperty).not.toHaveBeenCalled();
  });
});
