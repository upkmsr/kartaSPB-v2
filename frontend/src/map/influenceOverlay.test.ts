import { expect, it, vi } from "vitest";
import type { PreparedInfluence } from "../api/influence";
import { factorRegistry } from "../analysis/factorRegistry";
import type { IndependentLayerState } from "../analysis/analysisPreferences";
import {
  INFLUENCE_SOURCE_ID,
  influenceLayerId,
  updateInfluenceOverlay,
} from "./influenceOverlay";

const prepared: PreparedInfluence = {
  grid_version: "spb-square-200m-v1",
  influence_signature: "a".repeat(64),
  spec: "immutable",
  cell_count: 36292,
  channels: factorRegistry.slice(0, 2).map((factor, index) => ({
    metric_key: factor.metricKey,
    score_run_id: `00000000-0000-0000-0000-${index + 1}`.padEnd(36, "0"),
    property_name: `score_${index}`,
  })),
  tile_url_template: "/api/analysis/influence/tiles/a/{z}/{x}/{y}.mvt?spec=immutable",
  delivery_version: "influence-mvt-v1",
};

const state = (schoolMin = 60): Record<string, IndependentLayerState> => ({
  kindergarten: { enabled: true, minimumScore: 30 },
  school: { enabled: true, minimumScore: schoolMin },
});

const mockMap = () => {
  const sources = new Map<string, unknown>();
  const layers = new Map<string, unknown>([["water-fill", {}]]);
  return {
    sources,
    layers,
    addSource: vi.fn((id: string, source: unknown) => sources.set(id, source)),
    addLayer: vi.fn((layer: { id: string }, before?: string) => layers.set(layer.id, { ...layer, before })),
    getSource: (id: string) => sources.get(id),
    getLayer: (id: string) => layers.get(id),
    removeSource: vi.fn((id: string) => sources.delete(id)),
    removeLayer: vi.fn((id: string) => layers.delete(id)),
    setFilter: vi.fn(),
    setPaintProperty: vi.fn(),
  };
};

it("installs all enabled factors from one immutable vector source", () => {
  const map = mockMap();
  updateInfluenceOverlay(map as never, {
    prepared,
    layers: state(),
    accentedFactorId: null,
  }, "water-fill");
  expect(map.addSource).toHaveBeenCalledOnce();
  expect(map.sources.get(INFLUENCE_SOURCE_ID)).toEqual(expect.objectContaining({
    type: "vector",
    tiles: [prepared.tile_url_template],
    minzoom: 8,
  }));
  expect(map.layers.has(influenceLayerId("kindergarten"))).toBe(true);
  expect(map.layers.has(influenceLayerId("school"))).toBe(true);
  expect(map.addLayer).toHaveBeenCalledTimes(2);
});

it("lowers one threshold to expand its visible zone without replacing the source", () => {
  const map = mockMap();
  updateInfluenceOverlay(map as never, { prepared, layers: state(70), accentedFactorId: null });
  updateInfluenceOverlay(map as never, { prepared, layers: state(20), accentedFactorId: null });
  expect(map.addSource).toHaveBeenCalledOnce();
  expect(map.removeSource).not.toHaveBeenCalled();
  expect(map.setFilter).toHaveBeenCalledWith(
    influenceLayerId("school"),
    [">=", ["get", "score_1"], 20],
  );
  expect(map.setFilter).toHaveBeenCalledWith(
    influenceLayerId("kindergarten"),
    [">=", ["get", "score_0"], 30],
  );
});

it("removes only disabled factor layers and fully cleans up when hidden", () => {
  const map = mockMap();
  updateInfluenceOverlay(map as never, { prepared, layers: state(), accentedFactorId: null });
  updateInfluenceOverlay(map as never, {
    prepared,
    layers: { ...state(), school: { ...state().school, enabled: false } },
    accentedFactorId: null,
  });
  expect(map.layers.has(influenceLayerId("school"))).toBe(false);
  expect(map.layers.has(influenceLayerId("kindergarten"))).toBe(true);
  updateInfluenceOverlay(map as never, null);
  expect(map.sources.has(INFLUENCE_SOURCE_ID)).toBe(false);
});

it("removes the vector source when the last enabled factor is disabled", () => {
  const map = mockMap();
  updateInfluenceOverlay(map as never, { prepared, layers: state(), accentedFactorId: null });
  updateInfluenceOverlay(map as never, {
    prepared,
    layers: {
      kindergarten: { enabled: false, minimumScore: 30 },
      school: { enabled: false, minimumScore: 60 },
    },
    accentedFactorId: null,
  });
  expect(map.sources.has(INFLUENCE_SOURCE_ID)).toBe(false);
  expect(map.layers.has(influenceLayerId("kindergarten"))).toBe(false);
  expect(map.layers.has(influenceLayerId("school"))).toBe(false);
});
