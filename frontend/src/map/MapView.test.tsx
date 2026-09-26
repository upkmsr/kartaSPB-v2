import { act, render } from "@testing-library/react";
import * as maplibregl from "maplibre-gl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defaultVisibleLayerIds } from "./layerRegistry";
import { MapView } from "./MapView";
import type { CatalogFeatureCollection } from "./mapTypes";

type MockSource = { setData: ReturnType<typeof vi.fn> };
type MockMapInstance = {
  handlers: Record<string, Array<(...args: unknown[]) => void>>;
  layers: Map<string, { id: string }>;
  source: MockSource | null;
  addedSourceData: unknown[];
  renderedFeatures: Array<{ id?: string | number; properties?: Record<string, unknown> }>;
  zoom: number;
  bounds: { west: number; south: number; east: number; north: number };
  emit: (event: string, value?: unknown) => void;
  setLayoutProperty: ReturnType<typeof vi.fn>;
  fitBounds: ReturnType<typeof vi.fn>;
  resize: ReturnType<typeof vi.fn>;
};

const mapMock = vi.hoisted(() => ({ instances: [] as MockMapInstance[] }));

vi.mock("maplibre-gl", () => {
  class MapMock {
    handlers: Record<string, Array<(...args: unknown[]) => void>> = {};
    layers = new Map<string, { id: string }>();
    source: MockSource | null = null;
    addedSourceData: unknown[] = [];
    renderedFeatures: Array<{ id?: string | number; properties?: Record<string, unknown> }> = [];
    canvas = document.createElement("canvas");
    zoom = 12;
    bounds = { west: 30.3, south: 59.93, east: 30.32, north: 59.945 };
    setLayoutProperty = vi.fn();
    fitBounds = vi.fn();
    resize = vi.fn();

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
    addSource(_id: string, source: { data: unknown }) {
      this.addedSourceData.push(source.data);
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
      return this.renderedFeatures;
    }
    getCanvas() {
      return this.canvas;
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
    setWorkerUrl: vi.fn(),
    getWorkerUrl: vi.fn(() => "/assets/maplibre-gl-worker.js"),
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
            canonical_id: "3f24df02-2d4c-4595-bc44-74e0c7af83cd",
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
        districtIds={[]}
        navigationRequest={null}
        selectedFeatureId={null}
        onFeatureSelect={vi.fn()}
        onVisibleFeatureIdsChange={vi.fn()}
        onRequestStateChange={vi.fn()}
        onZoomChange={vi.fn()}
      />,
    );
    const map = mapMock.instances[0];
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());

    expect(maplibregl.setWorkerUrl).toHaveBeenCalledWith(
      expect.stringContaining("maplibre-gl-worker"),
    );
    expect(map.source).not.toBeNull();
    expect(map.layers.has("water-fill")).toBe(true);
    expect(map.layers.has("school-point")).toBe(true);
    expect(map.layers.has("road-line")).toBe(true);
    expect(map.layers.has("selection-point")).toBe(true);
    expect(map.source?.setData).toHaveBeenCalledWith(featureCollection);
    expect(map.resize).toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledOnce();
    const requestUrl = new URL(String(fetchMock.mock.calls[0][0]), "http://localhost");
    expect(requestUrl.searchParams.get("categories")).toBe(
      "nature.water,nature.park,healthcare.hospital",
    );

    map.zoom = 16;
    act(() => map.emit("moveend"));
    await act(async () => vi.runAllTimersAsync());
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(map.addedSourceData).toHaveLength(1);
    const zoomedUrl = new URL(String(fetchMock.mock.calls[1][0]), "http://localhost");
    expect(zoomedUrl.searchParams.get("categories")).toContain("transport.road");
    expect(zoomedUrl.searchParams.get("categories")).toContain("transport.stop");
  });

  it("restores the latest collection after a style reload", async () => {
    const featureCollection: CatalogFeatureCollection = {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          id: "3f24df02-2d4c-4595-bc44-74e0c7af83cd",
          geometry: { type: "Polygon", coordinates: [] },
          properties: {
            canonical_id: "3f24df02-2d4c-4595-bc44-74e0c7af83cd",
            name: "Парк",
            categories: ["nature.park"],
            object_kind: "feature",
          },
        },
      ],
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(featureCollection), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    render(
      <MapView
        visibleLayerIds={defaultVisibleLayerIds()}
        districtIds={[]}
        navigationRequest={null}
        selectedFeatureId={null}
        onFeatureSelect={vi.fn()}
        onVisibleFeatureIdsChange={vi.fn()}
        onRequestStateChange={vi.fn()}
        onZoomChange={vi.fn()}
      />,
    );
    const map = mapMock.instances[0];
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());

    map.source = null;
    map.layers.clear();
    act(() => map.emit("style.load"));

    expect(map.addedSourceData.at(-1)).toEqual(featureCollection);
    expect(map.layers.has("water-fill")).toBe(true);
    expect(map.layers.has("selection-point")).toBe(true);
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
        districtIds={[]}
        navigationRequest={null}
        selectedFeatureId={null}
        onFeatureSelect={vi.fn()}
        onVisibleFeatureIdsChange={vi.fn()}
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
          properties: {
            canonical_id: "3f24df02-2d4c-4595-bc44-74e0c7af83cd",
            name: "Школа",
            categories: ["education.school"],
            object_kind: "feature",
          },
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
        districtIds={[]}
        navigationRequest={null}
        selectedFeatureId={null}
        onFeatureSelect={vi.fn()}
        onVisibleFeatureIdsChange={vi.fn()}
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

  it("selects the stable canonical UUID from properties after worker processing", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ type: "FeatureCollection", features: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const onFeatureSelect = vi.fn();
    render(
      <MapView
        visibleLayerIds={defaultVisibleLayerIds()}
        districtIds={[]}
        navigationRequest={null}
        selectedFeatureId={null}
        onFeatureSelect={onFeatureSelect}
        onVisibleFeatureIdsChange={vi.fn()}
        onRequestStateChange={vi.fn()}
        onZoomChange={vi.fn()}
      />,
    );
    const map = mapMock.instances[0];
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());

    map.renderedFeatures = [
      {
        id: 17,
        properties: { canonical_id: "c49e54e1-3481-4b07-9f81-0b161b57b62b" },
      },
    ];
    act(() => map.emit("click", { point: { x: 10, y: 10 } }));

    expect(onFeatureSelect).toHaveBeenCalledWith(
      "c49e54e1-3481-4b07-9f81-0b161b57b62b",
    );
  });

  it("reloads the existing pipeline with district UUIDs and fits requested bbox", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ type: "FeatureCollection", features: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const central = "161ba369-c548-5569-9cc2-679522090220";
    const primorsky = "230bcc6e-fb6a-5172-afe6-81f0736fb77b";
    const { rerender } = render(
      <MapView
        visibleLayerIds={defaultVisibleLayerIds()}
        districtIds={[]}
        navigationRequest={null}
        selectedFeatureId={null}
        onFeatureSelect={vi.fn()}
        onVisibleFeatureIdsChange={vi.fn()}
        onRequestStateChange={vi.fn()}
        onZoomChange={vi.fn()}
      />,
    );
    const map = mapMock.instances[0];
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());
    expect(new URL(String(fetchMock.mock.calls[0][0]), "http://localhost").searchParams.has("districts"))
      .toBe(false);

    rerender(
      <MapView
        visibleLayerIds={defaultVisibleLayerIds()}
        districtIds={[central, primorsky]}
        navigationRequest={{ sequence: 1, bbox: [29.95, 59.91, 30.41, 60.07] }}
        selectedFeatureId={null}
        onFeatureSelect={vi.fn()}
        onVisibleFeatureIdsChange={vi.fn()}
        onRequestStateChange={vi.fn()}
        onZoomChange={vi.fn()}
      />,
    );
    await act(async () => vi.runAllTimersAsync());

    const scopedUrl = new URL(String(fetchMock.mock.calls.at(-1)?.[0]), "http://localhost");
    expect(scopedUrl.searchParams.get("districts")).toBe(`${central},${primorsky}`);
    expect(map.fitBounds).toHaveBeenCalledWith(
      [
        [29.95, 59.91],
        [30.41, 60.07],
      ],
      { padding: 48, duration: 700 },
    );
  });
});
