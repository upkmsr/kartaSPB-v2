import { describe, expect, it } from "vitest";
import type { LayerDefinition, LayerGroup } from "./layerContract";
import { layerGroups, layerRegistry } from "./layerRegistry";
import { planCatalogViewport } from "./catalogLayerDriver";
import {
  assertValidLayerRegistry,
  buildInteractionIndex,
  catalogCategoryKeys,
  defaultLayerIds,
  enabledLayers,
  loadableLayers,
  partitionLayersByDriver,
  resolveMapSelection,
  validateLayerRegistry,
  waitingLayers,
} from "./layerRegistryHelpers";

const proofGroup: LayerGroup = { id: "proof", label: "Proof fixtures", order: 100 };

const referenceVector = {
  id: "planning-demo",
  label: "Planning demo",
  groupId: "proof",
  layerClass: "reference-vector",
  source: {
    type: "geojson",
    sourceId: "planning-demo-source",
    dataUrl: "/fixtures/planning-demo.geojson",
    loadParticipation: "independent",
    districtHandling: "source-managed",
  },
  defaultVisible: false,
  minZoom: 8,
  selection: { kind: "layer-feature", idProperty: "zone_id" },
  loadingStrategy: "static",
  time: { kind: "none" },
  legend: { kind: "fill", color: "#7f68d8", outlineColor: "#d7cfff" },
  opacity: {
    default: 0.65,
    adjustable: true,
    applyTo: [{ renderLayerId: "planning-demo-fill", paintProperty: "fill-opacity" }],
  },
  provenance: {
    kind: "official",
    sourceLabel: "Test-only official reference fixture",
  },
  renderDefinitions: [
    {
      id: "planning-demo-fill",
      order: 100,
      type: "fill",
      geometry: "polygon",
      paint: { "fill-color": "#7f68d8" },
    },
  ],
} satisfies LayerDefinition;

const temporalVector = {
  ...referenceVector,
  id: "temporal-demo",
  label: "Temporal demo",
  layerClass: "temporal-vector",
  source: {
    ...referenceVector.source,
    sourceId: "temporal-demo-source",
    dataUrl: "/fixtures/temporal-demo.geojson",
  },
  selection: { kind: "layer-feature", idProperty: "event_id" },
  time: { kind: "range", startProperty: "valid_from", endProperty: "valid_to" },
  opacity: { default: 1, adjustable: false, applyTo: [] },
  renderDefinitions: [
    {
      id: "temporal-demo-fill",
      order: 110,
      type: "fill",
      geometry: "polygon",
      paint: { "fill-color": "#d28a47", "fill-opacity": 0.5 },
    },
  ],
} satisfies LayerDefinition;

const rasterLayer = {
  id: "raster-demo",
  label: "Raster demo",
  groupId: "proof",
  layerClass: "raster",
  source: {
    type: "raster-tile",
    sourceId: "raster-demo-source",
    tiles: ["/fixtures/raster/{z}/{x}/{y}.png"],
    tileSize: 256,
    loadParticipation: "maplibre-native",
    districtHandling: "ignored",
  },
  defaultVisible: false,
  minZoom: 5,
  maxZoom: 18,
  selection: { kind: "none" },
  loadingStrategy: "tiles",
  time: { kind: "none" },
  legend: { kind: "raster-gradient", colors: ["#132a45", "#e6df80"] },
  opacity: {
    default: 0.72,
    adjustable: true,
    applyTo: [{ renderLayerId: "raster-demo-layer", paintProperty: "raster-opacity" }],
  },
  renderDefinitions: [
    { id: "raster-demo-layer", order: 120, type: "raster", paint: {} },
  ],
} satisfies LayerDefinition;

const derivedAnalysis = {
  ...referenceVector,
  id: "viewshed-demo",
  label: "Viewshed demo",
  layerClass: "derived-analysis",
  source: {
    type: "derived",
    sourceId: "viewshed-demo-source",
    delivery: { type: "geojson", dataUrl: "/fixtures/viewshed-demo.geojson" },
    loadParticipation: "independent",
    districtHandling: "source-managed",
  },
  selection: { kind: "none" },
  opacity: {
    default: 0.5,
    adjustable: true,
    applyTo: [{ renderLayerId: "viewshed-demo-fill", paintProperty: "fill-opacity" }],
  },
  provenance: { kind: "derived", sourceLabel: "Test-only derived analysis" },
  renderDefinitions: [
    {
      id: "viewshed-demo-fill",
      order: 130,
      type: "fill",
      geometry: "polygon",
      paint: { "fill-color": "#60d8aa" },
    },
  ],
} satisfies LayerDefinition;

const vectorTiles = {
  ...referenceVector,
  id: "vector-tiles-demo",
  source: {
    type: "vector-tile",
    sourceId: "vector-tiles-demo-source",
    tiles: ["/fixtures/vector/{z}/{x}/{y}.pbf"],
    loadParticipation: "maplibre-native",
    districtHandling: "ignored",
  },
  loadingStrategy: "tiles",
  opacity: { default: 1, adjustable: false, applyTo: [] },
  renderDefinitions: [
    {
      id: "vector-tiles-demo-fill",
      order: 140,
      type: "fill",
      geometry: "polygon",
      sourceLayer: "zones",
      paint: { "fill-color": "#6688cc" },
    },
  ],
} satisfies LayerDefinition;

const proofRegistry: readonly LayerDefinition[] = [
  layerRegistry[0],
  referenceVector,
  temporalVector,
  rasterLayer,
  derivedAnalysis,
  vectorTiles,
];
const proofGroups = [...layerGroups, proofGroup];

describe("layer extension contract", () => {
  it("validates current catalog and all five semantic layer classes", () => {
    expect(() => assertValidLayerRegistry(layerRegistry, layerGroups)).not.toThrow();
    expect(() => assertValidLayerRegistry(proofRegistry, proofGroups)).not.toThrow();
    expect(new Set(proofRegistry.map((layer) => layer.layerClass))).toEqual(
      new Set([
        "canonical-object",
        "reference-vector",
        "temporal-vector",
        "raster",
        "derived-analysis",
      ]),
    );
  });

  it("derives enabled, loadable, waiting, defaults, and catalog aggregation purely", () => {
    const enabled = new Set(["water", "road", "planning-demo"]);
    const registry = [...layerRegistry, referenceVector];
    expect(enabledLayers(registry, enabled).map((layer) => layer.id)).toEqual([
      "water",
      "road",
      "planning-demo",
    ]);
    expect(loadableLayers(registry, enabled, 12).map((layer) => layer.id)).toEqual([
      "water",
      "planning-demo",
    ]);
    expect(waitingLayers(registry, enabled, 12).map((layer) => layer.id)).toEqual(["road"]);
    expect(catalogCategoryKeys(registry, enabled, 12)).toEqual(["nature.water"]);
    expect(defaultLayerIds(layerRegistry).has("boundary")).toBe(false);
  });

  it("partitions source drivers without catalog assumptions", () => {
    const partitions = partitionLayersByDriver(proofRegistry);
    expect([...partitions.keys()]).toEqual([
      "catalog",
      "geojson",
      "raster-tile",
      "derived",
      "vector-tile",
    ]);
  });

  it("plans one aggregated S6 catalog request independently of other drivers", () => {
    const plan = planCatalogViewport(
      [...layerRegistry, referenceVector, rasterLayer],
      new Set(["water", "park", "road", "planning-demo", "raster-demo"]),
      12,
    );
    expect(plan.enabledLayerIds).toEqual(["water", "park", "road"]);
    expect(plan.loadableLayerIds).toEqual(["water", "park"]);
    expect(plan.categoryKeys).toEqual(["nature.water", "nature.park"]);
  });

  it("resolves canonical and layer-feature selections and excludes raster", () => {
    const index = buildInteractionIndex(proofRegistry);
    expect(
      resolveMapSelection(
        "water-fill",
        { properties: { representative_canonical_id: "canonical-1" } },
        index,
      ),
    ).toEqual({ kind: "canonical-object", objectId: "canonical-1" });
    expect(
      resolveMapSelection(
        "planning-demo-fill",
        { id: "fallback", properties: { zone_id: 42 } },
        index,
      ),
    ).toEqual({ kind: "layer-feature", layerId: "planning-demo", featureId: "42" });
    expect(resolveMapSelection("raster-demo-layer", { id: "pixel" }, index)).toBeNull();
  });

  it("rejects duplicate logical and render IDs", () => {
    const duplicateLayer = { ...referenceVector, renderDefinitions: temporalVector.renderDefinitions };
    const errors = validateLayerRegistry(
      [referenceVector, duplicateLayer, temporalVector],
      [proofGroup],
    );
    expect(errors).toContain("Duplicate logical layer ID: planning-demo");
    expect(errors).toContain("Duplicate render layer ID: temporal-demo-fill");
  });

  it("rejects unknown groups, invalid zoom, opacity, and opacity mappings", () => {
    const invalid = {
      ...referenceVector,
      groupId: "missing",
      minZoom: -1,
      maxZoom: -2,
      opacity: {
        default: 1.5,
        adjustable: true,
        applyTo: [{ renderLayerId: "missing-render", paintProperty: "fill-opacity" as const }],
      },
    };
    const errors = validateLayerRegistry([invalid], [proofGroup]);
    expect(errors).toContain("Unknown group for planning-demo: missing");
    expect(errors).toContain("Invalid minZoom for planning-demo");
    expect(errors).toContain("Invalid maxZoom for planning-demo");
    expect(errors).toContain("Invalid opacity for planning-demo");
    expect(errors).toContain("Unknown opacity render layer for planning-demo: missing-render");
  });

  it("rejects missing source and incompatible source/loading strategies", () => {
    const invalid = {
      ...referenceVector,
      source: { ...referenceVector.source, sourceId: "", dataUrl: "" },
      loadingStrategy: "tiles" as const,
    };
    const errors = validateLayerRegistry([invalid], [proofGroup]);
    expect(errors).toContain("Missing source configuration for planning-demo");
    expect(errors).toContain("Missing GeoJSON URL for planning-demo");
    expect(errors).toContain("Invalid GeoJSON source/loading strategy for planning-demo");
  });

  it("rejects invalid selection and time-awareness combinations", () => {
    const invalidCatalog = {
      ...layerRegistry[0],
      selection: { kind: "none" as const },
    };
    const invalidTemporal = { ...temporalVector, time: { kind: "none" as const } };
    const errors = validateLayerRegistry([invalidCatalog, invalidTemporal], proofGroups);
    expect(errors).toContain("Invalid catalog selection semantics for water");
    expect(errors).toContain("Temporal layer requires time metadata: temporal-demo");
  });
});
