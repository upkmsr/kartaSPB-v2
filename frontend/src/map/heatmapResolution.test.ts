import { expect, it } from "vitest";
import {
  DETAIL_GRID_VERSION,
  OVERVIEW_GRID_VERSION,
  resolveHeatmapGridVersion,
} from "./heatmapResolution";

it("resolves manual and automatic heatmap grid versions", () => {
  expect(resolveHeatmapGridVersion("200m", 18)).toBe(OVERVIEW_GRID_VERSION);
  expect(resolveHeatmapGridVersion("50m", 11)).toBe(DETAIL_GRID_VERSION);
  expect(resolveHeatmapGridVersion("auto", 12.99)).toBe(OVERVIEW_GRID_VERSION);
  expect(resolveHeatmapGridVersion("auto", 13)).toBe(DETAIL_GRID_VERSION);
});
