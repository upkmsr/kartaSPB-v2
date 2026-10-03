import { expect, it, vi } from "vitest";
import type { Map as MapLibreMap } from "maplibre-gl";
import type { LayerDefinition } from "./layerContract";
import { installRegisteredLayers, setRegisteredLayerVisibility } from "./layerRuntime";
import { EMPTY_FEATURE_COLLECTION } from "./mapTypes";

const common = {
  groupId: "proof",
  defaultVisible: false,
  minZoom: 0,
  selection: { kind: "none" as const },
  time: { kind: "none" as const },
  provenance: { kind: "internal" as const, sourceLabel: "Test fixture" },
};

const fixtures: readonly LayerDefinition[] = [
  {
    ...common,
    id: "reference-runtime",
    label: "Reference runtime",
    layerClass: "reference-vector",
    source: {
      type: "geojson",
      sourceId: "reference-runtime-source",
      dataUrl: "/fixtures/reference.geojson",
      loadParticipation: "independent",
      districtHandling: "ignored",
    },
    loadingStrategy: "static",
    legend: { kind: "fill", color: "#6688cc" },
    opacity: {
      default: 0.6,
      adjustable: true,
      applyTo: [{ renderLayerId: "reference-runtime-fill", paintProperty: "fill-opacity" }],
    },
    renderDefinitions: [
      {
        id: "reference-runtime-fill",
        order: 1,
        type: "fill",
        geometry: "polygon",
        paint: { "fill-color": "#6688cc" },
      },
    ],
  },
  {
    ...common,
    id: "vector-runtime",
    label: "Vector runtime",
    layerClass: "reference-vector",
    source: {
      type: "vector-tile",
      sourceId: "vector-runtime-source",
      tiles: ["/fixtures/vector/{z}/{x}/{y}.pbf"],
      loadParticipation: "maplibre-native",
      districtHandling: "ignored",
    },
    loadingStrategy: "tiles",
    legend: { kind: "line", color: "#55cc88" },
    opacity: { default: 1, adjustable: false, applyTo: [] },
    renderDefinitions: [
      {
        id: "vector-runtime-line",
        order: 2,
        type: "line",
        geometry: "line",
        sourceLayer: "features",
        paint: { "line-color": "#55cc88" },
      },
    ],
  },
  {
    ...common,
    id: "raster-runtime",
    label: "Raster runtime",
    layerClass: "raster",
    source: {
      type: "raster-tile",
      sourceId: "raster-runtime-source",
      tiles: ["/fixtures/raster/{z}/{x}/{y}.png"],
      loadParticipation: "maplibre-native",
      districtHandling: "ignored",
    },
    loadingStrategy: "tiles",
    legend: { kind: "raster-gradient", colors: ["#000", "#fff"] },
    opacity: { default: 0.7, adjustable: true, applyTo: [] },
    renderDefinitions: [{ id: "raster-runtime-layer", order: 3, type: "raster" }],
  },
  {
    ...common,
    id: "derived-runtime",
    label: "Derived runtime",
    layerClass: "derived-analysis",
    source: {
      type: "derived",
      sourceId: "derived-runtime-source",
      delivery: { type: "geojson", dataUrl: "/fixtures/derived.geojson" },
      loadParticipation: "independent",
      districtHandling: "source-managed",
    },
    loadingStrategy: "static",
    legend: { kind: "fill", color: "#cc6688" },
    opacity: { default: 1, adjustable: false, applyTo: [] },
    renderDefinitions: [
      {
        id: "derived-runtime-fill",
        order: 4,
        type: "fill",
        geometry: "polygon",
        paint: { "fill-color": "#cc6688" },
      },
    ],
  },
];

it("installs supported source drivers and render layers without MapView branches", () => {
  const sources = new Map<string, unknown>();
  const layers = new Map<string, unknown>();
  const map = {
    getSource: (id: string) => sources.get(id),
    addSource: vi.fn((id: string, source: unknown) => sources.set(id, source)),
    getLayer: (id: string) => layers.get(id),
    addLayer: vi.fn((layer: { id: string }) => layers.set(layer.id, layer)),
    setPaintProperty: vi.fn(),
    setLayoutProperty: vi.fn(),
  } as unknown as MapLibreMap;

  installRegisteredLayers(map, fixtures, new Set(["reference-runtime"]), {
    catalogData: EMPTY_FEATURE_COLLECTION,
    selectedCanonicalId: null,
  });

  expect([...sources.keys()]).toEqual([
    "reference-runtime-source",
    "vector-runtime-source",
    "raster-runtime-source",
    "derived-runtime-source",
  ]);
  expect([...layers.keys()]).toEqual([
    "reference-runtime-fill",
    "vector-runtime-line",
    "raster-runtime-layer",
    "derived-runtime-fill",
  ]);
  expect(map.addSource).toHaveBeenCalledWith(
    "raster-runtime-source",
    expect.objectContaining({ type: "raster", tileSize: 256 }),
  );
  expect(map.setPaintProperty).toHaveBeenCalledWith(
    "reference-runtime-fill",
    "fill-opacity",
    0.6,
  );

  setRegisteredLayerVisibility(map, fixtures, new Set(["raster-runtime"]));
  expect(map.setLayoutProperty).toHaveBeenCalledWith(
    "raster-runtime-layer",
    "visibility",
    "visible",
  );
  expect(map.setLayoutProperty).toHaveBeenCalledWith(
    "reference-runtime-fill",
    "visibility",
    "none",
  );
});
