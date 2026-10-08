import { act, render } from "@testing-library/react";
import * as maplibregl from "maplibre-gl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defaultVisibleLayerIds, renderLayerIds } from "./layerRegistry";
import { MapView } from "./MapView";
import type { CatalogFeatureCollection } from "./mapTypes";

type MockSource = { setData: ReturnType<typeof vi.fn> };
type MockMapInstance = {
  handlers: Record<string, Array<(...args: unknown[]) => void>>;
  layers: Map<string, { id: string }>;
  source: MockSource | null;
  districtSource: MockSource | null;
  addedSourceData: unknown[];
  addedDistrictSourceData: unknown[];
  renderedFeatures: Array<{
    id?: string | number;
    properties?: Record<string, unknown>;
    layer?: { id: string };
  }>;
  zoom: number;
  bounds: { west: number; south: number; east: number; north: number };
  emit: (event: string, value?: unknown) => void;
  getStyle: () => { version: 8; sources: Record<string, never>; layers: [] };
  setLayoutProperty: ReturnType<typeof vi.fn>;
  fitBounds: ReturnType<typeof vi.fn>;
  flyTo: ReturnType<typeof vi.fn>;
  resize: ReturnType<typeof vi.fn>;
  setFilter: ReturnType<typeof vi.fn>;
  setPaintProperty: ReturnType<typeof vi.fn>;
};

const mapMock = vi.hoisted(() => ({ instances: [] as MockMapInstance[] }));

vi.mock("maplibre-gl", () => {
  class MapMock {
    handlers: Record<string, Array<(...args: unknown[]) => void>> = {};
    layers = new Map<string, { id: string }>();
    source: MockSource | null = null;
    districtSource: MockSource | null = null;
    addedSourceData: unknown[] = [];
    addedDistrictSourceData: unknown[] = [];
    renderedFeatures: Array<{
      id?: string | number;
      properties?: Record<string, unknown>;
      layer?: { id: string };
    }> = [];
    canvas = document.createElement("canvas");
    zoom = 12;
    bounds = { west: 30.3, south: 59.93, east: 30.32, north: 59.945 };
    setLayoutProperty = vi.fn();
    fitBounds = vi.fn();
    flyTo = vi.fn();
    resize = vi.fn();
    setFilter = vi.fn();
    setPaintProperty = vi.fn();

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
    getSource(id: string) {
      return id === "selected-districts" ? this.districtSource : this.source;
    }
    addSource(id: string, source: { data: unknown }) {
      if (id === "selected-districts") {
        this.addedDistrictSourceData.push(source.data);
        this.districtSource = { setData: vi.fn() };
      } else {
        this.addedSourceData.push(source.data);
        this.source = { setData: vi.fn() };
      }
    }
    getLayer(id: string) {
      return this.layers.get(id);
    }
    getStyle() {
      return { version: 8 as const, sources: {}, layers: [] as [] };
    }
    addLayer(layer: { id: string }) {
      this.layers.set(layer.id, layer);
    }
    removeLayer(id: string) {
      this.layers.delete(id);
    }
    removeSource(id: string) {
      if (id === "selected-districts") this.districtSource = null;
      else this.source = null;
    }
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
        onSelection={vi.fn()}
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
    expect(map.districtSource).not.toBeNull();
    expect(map.layers.has("water-fill")).toBe(true);
    expect(map.layers.has("school-point")).toBe(true);
    expect(map.layers.has("road-line")).toBe(true);
    expect(renderLayerIds.every((id) => map.layers.has(id))).toBe(true);
    expect(map.layers.has("selection-point")).toBe(true);
    expect(map.layers.has("selected-district-fill")).toBe(true);
    expect(map.layers.has("selected-district-outline")).toBe(true);
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

  it("keeps all facility members selectable while clicking the representative", async () => {
    const pointId = "3f24df02-2d4c-4595-bc44-74e0c7af83cd";
    const areaId = "0014437e-092b-479f-a006-10c926604682";
    const entityId = "9f3f27a5-950f-5c24-adce-5fe4db2c36c7";
    const onSelection = vi.fn();
    const onVisibleFeatureIdsChange = vi.fn();
    const featureCollection: CatalogFeatureCollection = {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          id: entityId,
          geometry: { type: "Polygon", coordinates: [] },
          properties: {
            canonical_id: pointId,
            facility_entity_id: entityId,
            representative_canonical_id: pointId,
            display_canonical_id: areaId,
            member_canonical_ids: [pointId, areaId],
            name: "СМ-Клиника",
            categories: ["healthcare.clinic"],
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
        selectedFeatureId={areaId}
        onSelection={onSelection}
        onVisibleFeatureIdsChange={onVisibleFeatureIdsChange}
        onRequestStateChange={vi.fn()}
        onZoomChange={vi.fn()}
      />,
    );
    const map = mapMock.instances[0];
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());

    expect(onVisibleFeatureIdsChange).toHaveBeenLastCalledWith(new Set([pointId, areaId]));
    map.renderedFeatures = [
      {
        layer: { id: "clinic-fill" },
        properties: { canonical_id: pointId, representative_canonical_id: pointId },
      },
    ];
    act(() => map.emit("click", { point: { x: 1, y: 1 } }));
    expect(onSelection).toHaveBeenCalledWith({
      kind: "canonical-object",
      objectId: pointId,
    });
    expect(JSON.stringify(map.layers.get("selection-fill"))).toContain(
      JSON.stringify(["in", areaId, ["get", "member_canonical_ids"]]),
    );
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
        onSelection={vi.fn()}
        onVisibleFeatureIdsChange={vi.fn()}
        onRequestStateChange={vi.fn()}
        onZoomChange={vi.fn()}
      />,
    );
    const map = mapMock.instances[0];
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());

    map.source = null;
    map.districtSource = null;
    map.layers.clear();
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());

    expect(map.addedSourceData.at(-1)).toEqual(featureCollection);
    expect(map.layers.has("water-fill")).toBe(true);
    expect(map.layers.has("selection-point")).toBe(true);
    expect(map.addedDistrictSourceData.at(-1)).toEqual({
      type: "FeatureCollection",
      features: [],
    });
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
  });

  it("clears stale source data on feature limits and bbox guard failures", async () => {
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
        onSelection={vi.fn()}
        onVisibleFeatureIdsChange={vi.fn()}
        onRequestStateChange={onRequestStateChange}
        onZoomChange={vi.fn()}
      />,
    );
    const map = mapMock.instances[0];
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());

    expect(onRequestStateChange).toHaveBeenLastCalledWith({ status: "feature-limit" });
    expect(map.source?.setData).toHaveBeenLastCalledWith({
      type: "FeatureCollection",
      features: [],
    });

    map.bounds = { west: 30, south: 59, east: 30.6, north: 59.1 };
    act(() => map.emit("moveend"));
    await act(async () => vi.runAllTimersAsync());
    expect(onRequestStateChange).toHaveBeenLastCalledWith({ status: "bbox-too-large" });
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(map.source?.setData).toHaveBeenLastCalledWith({
      type: "FeatureCollection",
      features: [],
    });
  });

  it("clears visible canonical IDs when the last enabled layer is disabled", async () => {
    const onVisibleFeatureIdsChange = vi.fn();
    const featureCollection: CatalogFeatureCollection = {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          id: "0014437e-092b-479f-a006-10c926604682",
          geometry: { type: "Polygon", coordinates: [] },
          properties: {
            canonical_id: "0014437e-092b-479f-a006-10c926604682",
            name: "Парк",
            categories: ["nature.park"],
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
    const { rerender } = render(
      <MapView
        visibleLayerIds={defaultVisibleLayerIds()}
        districtIds={[]}
        navigationRequest={null}
        selectedFeatureId="0014437e-092b-479f-a006-10c926604682"
        onSelection={vi.fn()}
        onVisibleFeatureIdsChange={onVisibleFeatureIdsChange}
        onRequestStateChange={vi.fn()}
        onZoomChange={vi.fn()}
      />,
    );
    const map = mapMock.instances[0];
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());
    expect(onVisibleFeatureIdsChange).toHaveBeenLastCalledWith(
      new Set(["0014437e-092b-479f-a006-10c926604682"]),
    );

    rerender(
      <MapView
        visibleLayerIds={new Set()}
        districtIds={[]}
        navigationRequest={null}
        selectedFeatureId="0014437e-092b-479f-a006-10c926604682"
        onSelection={vi.fn()}
        onVisibleFeatureIdsChange={onVisibleFeatureIdsChange}
        onRequestStateChange={vi.fn()}
        onZoomChange={vi.fn()}
      />,
    );
    await act(async () => vi.runAllTimersAsync());

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(map.source?.setData).toHaveBeenLastCalledWith({
      type: "FeatureCollection",
      features: [],
    });
    expect(onVisibleFeatureIdsChange).toHaveBeenLastCalledWith(new Set());
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
        onSelection={vi.fn()}
        onVisibleFeatureIdsChange={vi.fn()}
        onRequestStateChange={onRequestStateChange}
        onZoomChange={vi.fn()}
      />,
    );
    const map = mapMock.instances[0];
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());
    expect(map.source?.setData).toHaveBeenCalledTimes(1);

    map.bounds.east = 30.321;
    act(() => map.emit("moveend"));
    await act(async () => vi.runAllTimersAsync());
    expect(onRequestStateChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: "stale-error" }),
    );
    expect(map.source?.setData).toHaveBeenCalledTimes(1);

    map.bounds.east = 30.322;
    act(() => map.emit("moveend"));
    await act(async () => vi.runAllTimersAsync());
    expect(onRequestStateChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: "empty" }),
    );
    expect(map.source?.setData).toHaveBeenCalledTimes(2);
  });

  it("does not request while auto-load is off and loads latest state once on demand", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ type: "FeatureCollection", features: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const onRequestStateChange = vi.fn();
    const baseProps = {
      visibleLayerIds: defaultVisibleLayerIds(),
      autoLoad: false,
      districtIds: [] as string[],
      navigationRequest: null,
      selectedFeatureId: null,
      onSelection: vi.fn(),
      onVisibleFeatureIdsChange: vi.fn(),
      onRequestStateChange,
      onZoomChange: vi.fn(),
    };
    const { rerender } = render(<MapView {...baseProps} manualLoadSequence={0} />);
    const map = mapMock.instances[0];
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());

    expect(fetchMock).not.toHaveBeenCalled();
    expect(onRequestStateChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: "pending-manual-load" }),
    );

    const central = "161ba369-c548-5569-9cc2-679522090220";
    const selectedDistrictIds = [central];
    map.bounds.east = 30.321;
    act(() => map.emit("moveend"));
    await act(async () => vi.runAllTimersAsync());
    expect(fetchMock).not.toHaveBeenCalled();

    rerender(<MapView {...baseProps} districtIds={selectedDistrictIds} manualLoadSequence={0} />);
    await act(async () => vi.runAllTimersAsync());
    expect(
      fetchMock.mock.calls.filter(([request]) => String(request).includes("/api/map/features")),
    ).toHaveLength(0);
    expect(
      fetchMock.mock.calls.filter(([request]) =>
        String(request).includes("/api/districts/geometry"),
      ),
    ).toHaveLength(1);

    rerender(<MapView {...baseProps} districtIds={selectedDistrictIds} manualLoadSequence={1} />);
    await act(async () => vi.runAllTimersAsync());
    const mapCalls = fetchMock.mock.calls.filter(([request]) =>
      String(request).includes("/api/map/features"),
    );
    expect(mapCalls).toHaveLength(1);
    const manualUrl = new URL(String(mapCalls[0][0]), "http://localhost");
    expect(manualUrl.searchParams.get("bbox")).toBe("30.3,59.93,30.321,59.945");
    expect(manualUrl.searchParams.get("districts")).toBe(central);

    act(() => map.emit("moveend"));
    await act(async () => vi.runAllTimersAsync());
    expect(
      fetchMock.mock.calls.filter(([request]) => String(request).includes("/api/map/features")),
    ).toHaveLength(1);
  });

  it("debounces rapid viewport changes and deduplicates an identical loaded state", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
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
        onSelection={vi.fn()}
        onVisibleFeatureIdsChange={vi.fn()}
        onRequestStateChange={vi.fn()}
        onZoomChange={vi.fn()}
      />,
    );
    const map = mapMock.instances[0];
    act(() => map.emit("style.load"));
    map.bounds.east = 30.321;
    act(() => map.emit("moveend"));
    map.bounds.east = 30.322;
    act(() => map.emit("moveend"));
    await act(async () => vi.runAllTimersAsync());

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(
      new URL(String(fetchMock.mock.calls[0][0]), "http://localhost").searchParams.get("bbox"),
    ).toBe("30.3,59.93,30.322,59.945");

    act(() => map.emit("moveend"));
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("distinguishes no enabled layers from enabled layers waiting for zoom", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ type: "FeatureCollection", features: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const onRequestStateChange = vi.fn();
    const props = {
      autoLoad: true,
      manualLoadSequence: 0,
      districtIds: [] as string[],
      navigationRequest: null,
      selectedFeatureId: null,
      onSelection: vi.fn(),
      onVisibleFeatureIdsChange: vi.fn(),
      onRequestStateChange,
      onZoomChange: vi.fn(),
    };
    const { rerender } = render(<MapView {...props} visibleLayerIds={new Set()} />);
    const map = mapMock.instances[0];
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());
    expect(onRequestStateChange).toHaveBeenLastCalledWith({ status: "no-enabled-layers" });

    rerender(<MapView {...props} visibleLayerIds={new Set(["road"])} />);
    await act(async () => vi.runAllTimersAsync());
    expect(onRequestStateChange).toHaveBeenLastCalledWith({
      status: "waiting-for-zoom",
      waitingLayerIds: ["road"],
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("selects the stable canonical UUID from properties after worker processing", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ type: "FeatureCollection", features: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const onSelection = vi.fn();
    render(
      <MapView
        visibleLayerIds={defaultVisibleLayerIds()}
        districtIds={[]}
        navigationRequest={null}
        selectedFeatureId={null}
        onSelection={onSelection}
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
        layer: { id: "pharmacy-point" },
        properties: { canonical_id: "c49e54e1-3481-4b07-9f81-0b161b57b62b" },
      },
    ];
    act(() => map.emit("click", { point: { x: 10, y: 10 } }));

    expect(onSelection).toHaveBeenCalledWith({
      kind: "canonical-object",
      objectId: "c49e54e1-3481-4b07-9f81-0b161b57b62b",
    });
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
        onSelection={vi.fn()}
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
        navigationRequest={{
          sequence: 1,
          kind: "bbox",
          bbox: [29.95, 59.91, 30.41, 60.07],
        }}
        selectedFeatureId={null}
        onSelection={vi.fn()}
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
      { padding: 56, duration: 700, maxZoom: 17 },
    );
  });

  it("loads one exact geometry request for 1/N selections and clears the independent overlay", async () => {
    const central = "161ba369-c548-5569-9cc2-679522090220";
    const primorsky = "230bcc6e-fb6a-5172-afe6-81f0736fb77b";
    const selectedDistricts = [central, primorsky];
    const districtCollection = {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          id: central,
          properties: { id: central, name: "Центральный", slug: "centralny" },
          geometry: {
            type: "Polygon",
            coordinates: [[[30.3, 59.9], [30.4, 59.9], [30.3, 59.9]]],
          },
        },
      ],
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      return Promise.resolve(
        new Response(
          JSON.stringify(
            url.includes("/api/districts/geometry")
              ? districtCollection
              : { type: "FeatureCollection", features: [] },
          ),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    });
    const props = {
      visibleLayerIds: defaultVisibleLayerIds(),
      navigationRequest: null,
      selectedFeatureId: null,
      onSelection: vi.fn(),
      onVisibleFeatureIdsChange: vi.fn(),
      onRequestStateChange: vi.fn(),
      onZoomChange: vi.fn(),
    };
    const { rerender } = render(<MapView {...props} districtIds={[]} />);
    const map = mapMock.instances[0];
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());
    expect(
      fetchMock.mock.calls.filter(([request]) =>
        String(request).includes("/api/districts/geometry"),
      ),
    ).toHaveLength(0);

    rerender(<MapView {...props} districtIds={[central]} />);
    await act(async () => vi.runAllTimersAsync());
    let geometryCalls = fetchMock.mock.calls.filter(([request]) =>
      String(request).includes("/api/districts/geometry"),
    );
    expect(geometryCalls).toHaveLength(1);
    expect(
      new URL(String(geometryCalls[0][0]), "http://localhost").searchParams.get("districts"),
    ).toBe(central);
    expect(map.districtSource?.setData).toHaveBeenLastCalledWith(districtCollection);

    rerender(<MapView {...props} districtIds={selectedDistricts} />);
    await act(async () => vi.runAllTimersAsync());
    geometryCalls = fetchMock.mock.calls.filter(([request]) =>
      String(request).includes("/api/districts/geometry"),
    );
    expect(geometryCalls).toHaveLength(2);
    expect(
      new URL(String(geometryCalls[1][0]), "http://localhost").searchParams.get("districts"),
    ).toBe(`${central},${primorsky}`);

    rerender(
      <MapView {...props} visibleLayerIds={new Set()} districtIds={selectedDistricts} />,
    );
    await act(async () => vi.runAllTimersAsync());
    expect(map.layers.has("selected-district-fill")).toBe(true);
    expect(map.layers.has("selected-district-outline")).toBe(true);
    expect(map.districtSource?.setData).toHaveBeenLastCalledWith(districtCollection);

    rerender(<MapView {...props} visibleLayerIds={new Set()} districtIds={[]} />);
    await act(async () => vi.runAllTimersAsync());
    expect(map.districtSource?.setData).toHaveBeenLastCalledWith({
      type: "FeatureCollection",
      features: [],
    });
    expect(
      fetchMock.mock.calls.filter(([request]) =>
        String(request).includes("/api/districts/geometry"),
      ),
    ).toHaveLength(2);
  });

  it("keeps the map usable and overlay empty when selected geometry fails", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) =>
      String(input).includes("/api/districts/geometry")
        ? Promise.reject(new Error("district geometry unavailable"))
        : Promise.resolve(
            new Response(JSON.stringify({ type: "FeatureCollection", features: [] }), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            }),
          ),
    );
    const { rerender } = render(
      <MapView
        visibleLayerIds={defaultVisibleLayerIds()}
        districtIds={[]}
        navigationRequest={null}
        selectedFeatureId={null}
        onSelection={vi.fn()}
        onVisibleFeatureIdsChange={vi.fn()}
        onRequestStateChange={vi.fn()}
        onZoomChange={vi.fn()}
      />,
    );
    const map = mapMock.instances[0];
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());
    rerender(
      <MapView
        visibleLayerIds={defaultVisibleLayerIds()}
        districtIds={["161ba369-c548-5569-9cc2-679522090220"]}
        navigationRequest={null}
        selectedFeatureId={null}
        onSelection={vi.fn()}
        onVisibleFeatureIdsChange={vi.fn()}
        onRequestStateChange={vi.fn()}
        onZoomChange={vi.fn()}
      />,
    );
    await act(async () => vi.runAllTimersAsync());

    expect(map.districtSource?.setData).toHaveBeenLastCalledWith({
      type: "FeatureCollection",
      features: [],
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/districts/geometry"),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(map.layers.has("water-fill")).toBe(true);
  });

  it("flies to a point search navigation target", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ type: "FeatureCollection", features: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const { rerender } = render(
      <MapView
        visibleLayerIds={defaultVisibleLayerIds()}
        districtIds={[]}
        navigationRequest={null}
        selectedFeatureId={null}
        onSelection={vi.fn()}
        onVisibleFeatureIdsChange={vi.fn()}
        onRequestStateChange={vi.fn()}
        onZoomChange={vi.fn()}
      />,
    );
    const map = mapMock.instances[0];
    act(() => map.emit("style.load"));
    await act(async () => vi.runAllTimersAsync());

    rerender(
      <MapView
        visibleLayerIds={defaultVisibleLayerIds()}
        districtIds={[]}
        navigationRequest={{ sequence: 2, kind: "point", center: [30.3, 59.9], zoom: 16 }}
        selectedFeatureId={null}
        onSelection={vi.fn()}
        onVisibleFeatureIdsChange={vi.fn()}
        onRequestStateChange={vi.fn()}
        onZoomChange={vi.fn()}
      />,
    );

    expect(map.flyTo).toHaveBeenCalledWith({ center: [30.3, 59.9], zoom: 16, duration: 700 });
  });
});
