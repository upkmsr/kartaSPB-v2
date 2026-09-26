import { describe, expect, it } from "vitest";
import { featureFilter } from "@maplibre/maplibre-gl-style-spec";
import {
  activeCategoryKeys,
  categoryFilter,
  defaultVisibleLayerIds,
  enabledCategoryKeys,
  layerRegistry,
  orderedRenderDefinitions,
} from "./layerRegistry";

describe("layerRegistry", () => {
  it("defines the ten ordered logical layers and render definitions", () => {
    expect(layerRegistry.map((layer) => layer.id)).toEqual([
      "water",
      "park",
      "school",
      "kindergarten",
      "pharmacy",
      "hospital",
      "clinic",
      "road",
      "boundary",
      "stop",
    ]);
    expect(layerRegistry.every((layer) => layer.renderDefinitions.length > 0)).toBe(true);
    expect(layerRegistry.find((layer) => layer.id === "boundary")?.defaultVisible).toBe(false);
    const orderedIds = orderedRenderDefinitions.map((item) => item.definition.id);
    expect(orderedIds.indexOf("road-line")).toBeLessThan(orderedIds.indexOf("school-point"));
    expect(orderedIds.indexOf("boundary-line")).toBeLessThan(orderedIds.indexOf("stop-point"));
  });

  it("activates unique categories only for visible layers at their minimum zoom", () => {
    const visible = defaultVisibleLayerIds();

    expect(activeCategoryKeys(visible, 12)).toEqual([
      "nature.water",
      "nature.park",
      "healthcare.hospital",
    ]);
    expect(activeCategoryKeys(visible, 13)).toContain("education.school");
    expect(activeCategoryKeys(visible, 13)).not.toContain("healthcare.pharmacy");
    expect(activeCategoryKeys(visible, 15)).toContain("transport.stop");
    expect(activeCategoryKeys(visible, 15)).not.toContain("transport.road");
    expect(activeCategoryKeys(visible, 16)).toContain("transport.road");
  });

  it("uses enabled layers as search scope independently of map zoom", () => {
    const visible = new Set(["pharmacy", "road"]);
    expect(enabledCategoryKeys(visible)).toEqual([
      "healthcare.pharmacy",
      "transport.road",
    ]);
  });

  it("builds category and geometry filters", () => {
    expect(categoryFilter("education.school", "polygon")).toEqual([
      "all",
      ["in", "education.school", ["get", "categories"]],
      ["==", ["geometry-type"], "Polygon"],
    ]);
  });

  it("matches array categories and MapLibre polygon geometry", () => {
    const parkFilter = featureFilter(
      categoryFilter("nature.park", "polygon"),
      "layers[park-fill].filter",
    ).filter;

    expect(
      parkFilter(
        { zoom: 12 },
        { type: 3, properties: { categories: ["nature.park"] } } as never,
      ),
    ).toBe(true);
    expect(
      parkFilter(
        { zoom: 12 },
        { type: 3, properties: { categories: ["nature.water"] } } as never,
      ),
    ).toBe(false);
  });

  it("accepts real LineString water and road features only at their layer geometry", () => {
    const waterLineFilter = featureFilter(
      categoryFilter("nature.water", "line"),
      "layers[water-river-line].filter",
    ).filter;
    const roadLineFilter = featureFilter(
      categoryFilter("transport.road", "line"),
      "layers[road-line].filter",
    ).filter;
    const lineFeature = (category: string) =>
      ({ type: 2, properties: { categories: [category] } }) as never;

    expect(waterLineFilter({ zoom: 12 }, lineFeature("nature.water"))).toBe(true);
    expect(roadLineFilter({ zoom: 16 }, lineFeature("transport.road"))).toBe(true);
    expect(
      roadLineFilter(
        { zoom: 16 },
        { type: 3, properties: { categories: ["transport.road"] } } as never,
      ),
    ).toBe(false);
  });
});
