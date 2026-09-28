import { describe, expect, it, vi } from "vitest";
import { EMPTY_DISTRICT_GEOMETRY } from "../api/districts";
import {
  installSelectedDistrictOverlay,
  SELECTED_DISTRICT_FILL_LAYER_ID,
  SELECTED_DISTRICT_OUTLINE_LAYER_ID,
  SELECTED_DISTRICT_SOURCE_ID,
  setSelectedDistrictOverlayData,
} from "./districtOverlay";

describe("selected district MapLibre overlay", () => {
  it("installs an independent source, subtle fill, and zoom-independent outline in order", () => {
    const sources = new Map<string, unknown>();
    const layers = new Map<string, Record<string, unknown>>([
      ["water-fill", { id: "water-fill" }],
      ["selection-fill", { id: "selection-fill" }],
    ]);
    const beforeIds: Array<string | undefined> = [];
    const addSource = vi.fn((id: string, source: unknown) => sources.set(id, source));
    const addLayer = vi.fn((layer: Record<string, unknown>, beforeId?: string) => {
      beforeIds.push(beforeId);
      layers.set(String(layer.id), layer);
    });
    const map = {
      getSource: (id: string) => sources.get(id),
      addSource,
      getLayer: (id: string) => layers.get(id),
      addLayer,
    };

    installSelectedDistrictOverlay(
      map as never,
      EMPTY_DISTRICT_GEOMETRY,
      "water-fill",
      "selection-fill",
    );

    expect(addSource).toHaveBeenCalledWith(SELECTED_DISTRICT_SOURCE_ID, {
      type: "geojson",
      data: EMPTY_DISTRICT_GEOMETRY,
    });
    const fill = addLayer.mock.calls[0][0];
    const outline = addLayer.mock.calls[1][0];
    expect(beforeIds).toEqual(["water-fill", "selection-fill"]);
    expect(fill).toMatchObject({
      id: SELECTED_DISTRICT_FILL_LAYER_ID,
      source: SELECTED_DISTRICT_SOURCE_ID,
      type: "fill",
      paint: { "fill-opacity": 0.08 },
    });
    expect(outline).toMatchObject({
      id: SELECTED_DISTRICT_OUTLINE_LAYER_ID,
      source: SELECTED_DISTRICT_SOURCE_ID,
      type: "line",
    });
    expect(outline).not.toHaveProperty("minzoom");
    expect(outline.paint).toHaveProperty("line-width", [
      "interpolate",
      ["linear"],
      ["zoom"],
      7,
      3,
      10,
      2.5,
      14,
      1.8,
      18,
      1.4,
    ]);
  });

  it("updates only the dedicated district source", () => {
    const setData = vi.fn();
    const map = {
      getSource: (id: string) =>
        id === SELECTED_DISTRICT_SOURCE_ID ? { setData } : undefined,
    };

    setSelectedDistrictOverlayData(map as never, EMPTY_DISTRICT_GEOMETRY);

    expect(setData).toHaveBeenCalledWith(EMPTY_DISTRICT_GEOMETRY);
  });
});
