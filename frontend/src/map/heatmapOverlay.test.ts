import { expect, it, vi } from "vitest";
import type { PreparedHeatmap } from "../api/heatmap";
import {
  DEFAULT_HEATMAP_DISPLAY_RANGE,
  HEATMAP_LAYER_ID,
  HEATMAP_MIN_ZOOM,
  HEATMAP_SOURCE_ID,
  heatmapLegendValues,
  updateHeatmapOverlay,
} from "./heatmapOverlay";

const prepared = (signature: string): PreparedHeatmap => ({
  grid_version: "spb-square-200m-v1",
  weights: { "education.school.distance_m": 100 },
  scoring_signature: signature,
  spec: "opaque",
  cell_count: 36292,
  min: 0,
  max: 100,
  mean: 50,
  tile_url_template: `/api/analysis/heatmap/tiles/${signature}/{z}/{x}/{y}.mvt?spec=opaque`,
  delivery_version: "heatmap-mvt-v1",
});

const mockMap = () => {
  const sources = new Map<string, unknown>();
  const layers = new Map<string, unknown>([["analysis-grid-fill", {}]]);
  const addSource = vi.fn((id: string, source: unknown) => sources.set(id, source));
  const addLayer = vi.fn((layer: { id: string }, before?: string) => {
    layers.set(layer.id, { ...layer, before });
  });
  return {
    sources,
    layers,
    addSource,
    addLayer,
    getSource: (id: string) => sources.get(id),
    getLayer: (id: string) => layers.get(id),
    removeSource: vi.fn((id: string) => sources.delete(id)),
    removeLayer: vi.fn((id: string) => layers.delete(id)),
    setPaintProperty: vi.fn(),
  };
};

it("installs an absolute non-interactive fill below analysis and catalog layers", () => {
  const map = mockMap();
  updateHeatmapOverlay(
    map as never,
    prepared("a".repeat(64)),
    DEFAULT_HEATMAP_DISPLAY_RANGE,
    "analysis-grid-fill",
  );

  expect(HEATMAP_MIN_ZOOM).toBe(11);
  expect(map.sources.get(HEATMAP_SOURCE_ID)).toEqual(
    expect.objectContaining({ type: "vector", minzoom: 11 }),
  );
  expect(map.layers.get(HEATMAP_LAYER_ID)).toEqual(
    expect.objectContaining({
      type: "fill",
      minzoom: 11,
      "source-layer": "analysis_heatmap",
      before: "analysis-grid-fill",
      paint: expect.objectContaining({ "fill-opacity": 0.72 }),
    }),
  );
  expect(JSON.stringify(map.layers.get(HEATMAP_LAYER_ID))).toContain("#d73027");
  expect(JSON.stringify(map.layers.get(HEATMAP_LAYER_ID))).toContain("#1a9850");
  expect(heatmapLegendValues(DEFAULT_HEATMAP_DISPLAY_RANGE)).toEqual([
    40, 55, 70, 85, 100,
  ]);
});

it("changes contrast through paint only and replaces only a changed source", () => {
  const map = mockMap();
  const heatmap = prepared("a".repeat(64));
  updateHeatmapOverlay(map as never, heatmap, { min: 40, max: 100 });
  updateHeatmapOverlay(map as never, heatmap, { min: 40, max: 100 });
  expect(map.addSource).toHaveBeenCalledOnce();
  expect(map.addLayer).toHaveBeenCalledOnce();
  expect(map.setPaintProperty).not.toHaveBeenCalled();

  updateHeatmapOverlay(map as never, heatmap, { min: 25, max: 100 });
  expect(map.setPaintProperty).toHaveBeenCalledWith(
    HEATMAP_LAYER_ID,
    "fill-color",
    expect.any(Array),
  );
  expect(map.addSource).toHaveBeenCalledOnce();
  expect(map.addLayer).toHaveBeenCalledOnce();
  expect(map.removeSource).not.toHaveBeenCalled();

  updateHeatmapOverlay(map as never, prepared("b".repeat(64)), { min: 25, max: 100 });
  expect(map.removeLayer).toHaveBeenCalledWith(HEATMAP_LAYER_ID);
  expect(map.removeSource).toHaveBeenCalledWith(HEATMAP_SOURCE_ID);
  expect(map.addSource).toHaveBeenCalledTimes(2);
});

it("restores after style reload and removes the overlay when hidden", () => {
  const map = mockMap();
  const heatmap = prepared("a".repeat(64));
  updateHeatmapOverlay(map as never, heatmap);
  map.sources.clear();
  map.layers.delete(HEATMAP_LAYER_ID);
  updateHeatmapOverlay(map as never, heatmap);
  expect(map.addSource).toHaveBeenCalledTimes(2);

  updateHeatmapOverlay(map as never, null);
  expect(map.sources.has(HEATMAP_SOURCE_ID)).toBe(false);
  expect(map.layers.has(HEATMAP_LAYER_ID)).toBe(false);
});

it("never requests a 50 m source below z13", () => {
  const map = mockMap();
  updateHeatmapOverlay(
    map as never,
    { ...prepared("c".repeat(64)), grid_version: "spb-square-50m-v1" },
  );
  expect(map.sources.get(HEATMAP_SOURCE_ID)).toEqual(
    expect.objectContaining({ minzoom: 13 }),
  );
  expect(map.layers.get(HEATMAP_LAYER_ID)).toEqual(
    expect.objectContaining({ minzoom: 13 }),
  );
});
