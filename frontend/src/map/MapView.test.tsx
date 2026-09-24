import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defaultVisibleLayerIds } from "./layerRegistry";
import { MapView } from "./MapView";

type MockSource = { setData: ReturnType<typeof vi.fn> };
type MockMapInstance = {
  handlers: Record<string, Array<(...args: unknown[]) => void>>;
  layers: Map<string, { id: string }>;
  source: MockSource | null;
  zoom: number;
  bounds: { west: number; south: number; east: number; north: number };
  emit: (event: string, value?: unknown) => void;
  setLayoutProperty: ReturnType<typeof vi.fn>;
};

const mapMock = vi.hoisted(() => ({ instances: [] as MockMapInstance[] }));

vi.mock("maplibre-gl", () => {
  class MapMock {
    handlers: Record<string, Array<(...args: unknown[]) => void>> = {};
    layers = new Map<string, { id: string }>();
    source: MockSource | null = null;
    zoom = 12;
    bounds = { west: 30.3, south: 59.93, east: 30.32, north: 59.945 };
    setLayoutProperty = vi.fn();

    constructor() {
      mapMock.instances.push(this);
    }

    addControl() {}
    on(event: string, handler: (...args: unknown[]) => void) {
      this.handlers[event] ??= [];
      this.handlers[event].push(handler);
    }
    emit(event: string, value?: unknown) {
      for (const handler of this.handlers[event] ?? []) handler(value);
    }
    getSource() {
      return this.source;
    }
    addSource() {
      this.source = { setData: vi.fn() };
    }
    getLayer(id: string) {
      return this.layers.get(id);
    }
    addLayer(layer: { id: string }) {
      this.layers.set(layer.id, layer);
    }
    setFilter() {}
    getBounds() {
      return {
        getWest: () => this.bounds.west,
        getSouth: () => this.bounds.south,
        getEast: () => this.bounds.east,
        getNorth: () => this.bounds.north,
      };
    }
    getZoom() {
      return this.zoom;
    }
    queryRenderedFeatures() {
      return [];
    }
    getCanvas() {
      return { style: { cursor: "" } };
    }
    isStyleLoaded() {
      return true;
    }
    setStyle() {}
    remove() {}
  }

  return {
    Map: MapMock,
    NavigationControl: class {},
    ScaleControl: class {},
  };
});

describe("MapView MapLibre integration", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mapMock.instances.length = 0;
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("registers one source, creates render layers, and updates source data", async () => {
    const featureCollection = {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          id: "3f24df02-2d4c-4595-bc44-74e0c7af83cd",
          geometry: { type: "Point", coordinates: [30.31, 59.94] },
          properties: {
            name: "Школа",
            categories: ["education.school"],
            object_kind: "feature",
          },
        },
      ],
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(featureCollection), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    render(
      <MapView
        visibleLayerIds={defaultVisibleLayerIds()}
        selectedFeatureId={null}
        onFeatureSelect={vi.fn()}
        onRequestStateChange={vi.fn()}
        onZoomChange={vi.fn()}
      />,
    );
    const map = mapMock.instances[0];
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());

    expect(map.source).not.toBeNull();
    expect(map.layers.has("water-fill")).toBe(true);
    expect(map.layers.has("school-point")).toBe(true);
    expect(map.layers.has("road-line")).toBe(true);
    expect(map.layers.has("selection-point")).toBe(true);
    expect(map.source?.setData).toHaveBeenCalledWith(featureCollection);
    expect(fetchMock).toHaveBeenCalledOnce();
    const requestUrl = new URL(String(fetchMock.mock.calls[0][0]), "http://localhost");
    expect(requestUrl.searchParams.get("categories")).toBe(
      "nature.water,nature.park,healthcare.hospital",
    );

    map.zoom = 16;
    act(() => map.emit("moveend"));
    await act(async () => vi.runAllTimersAsync());
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const zoomedUrl = new URL(String(fetchMock.mock.calls[1][0]), "http://localhost");
    expect(zoomedUrl.searchParams.get("categories")).toContain("transport.road");
    expect(zoomedUrl.searchParams.get("categories")).toContain("transport.stop");
  });

  it("preserves source data on feature limits and bbox guard failures", async () => {
    const onRequestStateChange = vi.fn();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: { code: "feature_limit_exceeded", message: "too many" } }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    );
    render(
      <MapView
        visibleLayerIds={defaultVisibleLayerIds()}
        selectedFeatureId={null}
        onFeatureSelect={vi.fn()}
        onRequestStateChange={onRequestStateChange}
        onZoomChange={vi.fn()}
      />,
    );
    const map = mapMock.instances[0];
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());

    expect(onRequestStateChange).toHaveBeenLastCalledWith({ status: "feature-limit" });
    expect(map.source?.setData).not.toHaveBeenCalled();

    map.bounds = { west: 30, south: 59, east: 30.6, north: 59.1 };
    act(() => map.emit("moveend"));
    await act(async () => vi.runAllTimersAsync());
    expect(onRequestStateChange).toHaveBeenLastCalledWith({ status: "bbox-too-large" });
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(map.source?.setData).not.toHaveBeenCalled();
  });

  it("keeps the last successful source on failure and recovers with an empty result", async () => {
    const onRequestStateChange = vi.fn();
    const success = {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          id: "3f24df02-2d4c-4595-bc44-74e0c7af83cd",
          geometry: { type: "Point", coordinates: [30.31, 59.94] },
          properties: { name: "Школа", categories: ["education.school"], object_kind: "feature" },
        },
      ],
    };
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify(success), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockRejectedValueOnce(new Error("network unavailable"))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ type: "FeatureCollection", features: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    render(
      <MapView
        visibleLayerIds={defaultVisibleLayerIds()}
        selectedFeatureId={null}
        onFeatureSelect={vi.fn()}
        onRequestStateChange={onRequestStateChange}
        onZoomChange={vi.fn()}
      />,
    );
    const map = mapMock.instances[0];
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());
    expect(map.source?.setData).toHaveBeenCalledTimes(1);

    act(() => map.emit("moveend"));
    await act(async () => vi.runAllTimersAsync());
    expect(onRequestStateChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: "error" }),
    );
    expect(map.source?.setData).toHaveBeenCalledTimes(1);

    act(() => map.emit("moveend"));
    await act(async () => vi.runAllTimersAsync());
    expect(onRequestStateChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: "empty" }),
    );
    expect(map.source?.setData).toHaveBeenCalledTimes(2);
  });
});
