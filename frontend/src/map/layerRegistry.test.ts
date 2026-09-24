import { describe, expect, it } from "vitest";
import {
  activeCategoryKeys,
  categoryFilter,
  defaultVisibleLayerIds,
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

  it("builds category and geometry filters", () => {
    expect(categoryFilter("education.school", "polygon")).toEqual([
      "all",
      ["in", "education.school", ["get", "categories"]],
      ["==", ["geometry-type"], "Polygon"],
    ]);
  });
});
