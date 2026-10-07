import { expect, it, vi } from "vitest";
import type { PreparedHeatmap } from "../api/heatmap";
import {
  HEATMAP_LAYER_ID,
  HEATMAP_SOURCE_ID,
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
  };
};

it("installs an absolute non-interactive fill below analysis and catalog layers", () => {
  const map = mockMap();
  updateHeatmapOverlay(map as never, prepared("a".repeat(64)), "analysis-grid-fill");

  expect(map.sources.get(HEATMAP_SOURCE_ID)).toEqual(
    expect.objectContaining({ type: "vector", minzoom: 10 }),
  );
  expect(map.layers.get(HEATMAP_LAYER_ID)).toEqual(
    expect.objectContaining({
      type: "fill",
      minzoom: 10,
      "source-layer": "analysis_heatmap",
      before: "analysis-grid-fill",
      paint: expect.objectContaining({ "fill-opacity": 0.72 }),
    }),
  );
  expect(JSON.stringify(map.layers.get(HEATMAP_LAYER_ID))).toContain("#d73027");
  expect(JSON.stringify(map.layers.get(HEATMAP_LAYER_ID))).toContain("#1a9850");
});

it("does not reinstall the same signature and replaces a changed source", () => {
  const map = mockMap();
  updateHeatmapOverlay(map as never, prepared("a".repeat(64)), "analysis-grid-fill");
  updateHeatmapOverlay(map as never, prepared("a".repeat(64)), "analysis-grid-fill");
  expect(map.addSource).toHaveBeenCalledOnce();
  expect(map.addLayer).toHaveBeenCalledOnce();

  updateHeatmapOverlay(map as never, prepared("b".repeat(64)), "analysis-grid-fill");
  expect(map.removeLayer).toHaveBeenCalledWith(HEATMAP_LAYER_ID);
  expect(map.removeSource).toHaveBeenCalledWith(HEATMAP_SOURCE_ID);
  expect(map.addSource).toHaveBeenCalledTimes(2);
});

it("restores after style reload and removes the overlay when hidden", () => {
  const map = mockMap();
  const heatmap = prepared("a".repeat(64));
  updateHeatmapOverlay(map as never, heatmap, "analysis-grid-fill");
  map.sources.clear();
  map.layers.delete(HEATMAP_LAYER_ID);
  updateHeatmapOverlay(map as never, heatmap, "analysis-grid-fill");
  expect(map.addSource).toHaveBeenCalledTimes(2);

  updateHeatmapOverlay(map as never, null, "analysis-grid-fill");
  expect(map.sources.has(HEATMAP_SOURCE_ID)).toBe(false);
  expect(map.layers.has(HEATMAP_LAYER_ID)).toBe(false);
});
