import { expect, it } from "vitest";
import { layerRegistry } from "./layerRegistry";
import { minimumZoomForLayer, registryForPerformanceProfile } from "./performanceProfile";

it("applies bounded catalog zoom offsets and leaves derived layers unchanged", () => {
  const school = layerRegistry.find((layer) => layer.id === "school")!;
  const grid = layerRegistry.find((layer) => layer.id === "analysis-grid")!;
  expect(minimumZoomForLayer(school, "economy")).toBe(14);
  expect(minimumZoomForLayer(school, "balanced")).toBe(13);
  expect(minimumZoomForLayer(school, "detailed")).toBe(12);
  expect(minimumZoomForLayer(grid, "economy")).toBe(grid.minZoom);
  expect(registryForPerformanceProfile(layerRegistry, "detailed")).toHaveLength(
    layerRegistry.length,
  );
});
