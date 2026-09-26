import { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import type {
  FilterSpecification,
  GeoJSONSource,
  Map as MapLibreMap,
  StyleSpecification,
} from "maplibre-gl";
import {
  activeCategoryKeys,
  categoryFilter,
  geometryFilter,
  interactiveRenderLayerIds,
  layerRegistry,
  orderedRenderDefinitions,
} from "./layerRegistry";
import { guardBbox, LatestMapRequest, MapApiError } from "./mapApi";
import {
  EMPTY_FEATURE_COLLECTION,
  type CatalogFeatureCollection,
  type MapNavigationRequest,
  type MapRequestState,
} from "./mapTypes";

const SOURCE_ID = "catalog-features";
const INITIAL_CENTER: [number, number] = [30.3158, 59.9398];
const INITIAL_ZOOM = 12;
const VIEWPORT_DEBOUNCE_MS = 200;
const DEFAULT_STYLE_URL = "https://tiles.openfreemap.org/styles/dark";
const BASEMAP_ATTRIBUTION =
  '<a href="https://openfreemap.org" target="_blank">OpenFreeMap</a> ' +
  '<a href="https://www.openmaptiles.org/" target="_blank">© OpenMapTiles</a> ' +
  'Data from <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>';

const localDarkStyle: StyleSpecification = {
  version: 8,
  name: "KARTASPB local dark",
  sources: {},
  layers: [
    {
      id: "background",
      type: "background",
      paint: { "background-color": "#0d1213" },
    },
  ],
};

const configuredStyleUrl = import.meta.env.VITE_MAP_STYLE_URL?.trim();
const primaryStyleUrl =
  configuredStyleUrl === "local" ? null : configuredStyleUrl || DEFAULT_STYLE_URL;
const basemapAttribution = primaryStyleUrl === DEFAULT_STYLE_URL ? BASEMAP_ATTRIBUTION : undefined;

export type MapViewProps = {
  visibleLayerIds: ReadonlySet<string>;
  districtIds: readonly string[];
  navigationRequest: MapNavigationRequest | null;
  selectedFeatureId: string | null;
  onFeatureSelect: (objectId: string) => void;
  onVisibleFeatureIdsChange: (visibleIds: ReadonlySet<string>) => void;
  onRequestStateChange: (state: MapRequestState) => void;
  onZoomChange: (zoom: number) => void;
};

const selectedFilter = (
  geometry: "point" | "line" | "polygon",
  selectedId: string | null,
): FilterSpecification => [
  "all",
  geometryFilter(geometry),
  ["==", ["get", "canonical_id"], selectedId ?? ""],
];

const installCatalogLayers = (
  map: MapLibreMap,
  data: CatalogFeatureCollection,
  visibleLayerIds: ReadonlySet<string>,
  selectedId: string | null,
): void => {
  if (!map.getSource(SOURCE_ID)) {
    map.addSource(SOURCE_ID, { type: "geojson", data });
  }

  for (const { logicalLayer, definition } of orderedRenderDefinitions) {
    if (map.getLayer(definition.id)) continue;
    const visibility = visibleLayerIds.has(logicalLayer.id) ? "visible" : "none";
    const common = {
      id: definition.id,
      source: SOURCE_ID,
      minzoom: logicalLayer.minZoom,
      filter: categoryFilter(logicalLayer.categoryKey, definition.geometry),
      layout: { visibility } as const,
    };
    if (definition.type === "circle") {
      map.addLayer({ ...common, type: "circle", paint: definition.paint });
    } else if (definition.type === "fill") {
      map.addLayer({ ...common, type: "fill", paint: definition.paint });
    } else {
      map.addLayer({ ...common, type: "line", paint: definition.paint });
    }
  }

  if (!map.getLayer("selection-fill")) {
    map.addLayer({
      id: "selection-fill",
      source: SOURCE_ID,
      type: "fill",
      filter: selectedFilter("polygon", selectedId),
      paint: { "fill-color": "#bbff3c", "fill-opacity": 0.42 },
    });
    map.addLayer({
      id: "selection-line",
      source: SOURCE_ID,
      type: "line",
      filter: [
        "all",
        ["any", geometryFilter("line"), geometryFilter("polygon")],
        ["==", ["get", "canonical_id"], selectedId ?? ""],
      ],
      paint: { "line-color": "#bbff3c", "line-width": 4, "line-opacity": 1 },
    });
    map.addLayer({
      id: "selection-point",
      source: SOURCE_ID,
      type: "circle",
      filter: selectedFilter("point", selectedId),
      paint: {
        "circle-color": "#bbff3c",
        "circle-radius": 10,
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 2,
      },
    });
  }
};

const updateSelectionFilters = (map: MapLibreMap, selectedId: string | null): void => {
  if (!map.getLayer("selection-fill")) return;
  map.setFilter("selection-fill", selectedFilter("polygon", selectedId));
  map.setFilter("selection-line", [
    "all",
    ["any", geometryFilter("line"), geometryFilter("polygon")],
    ["==", ["get", "canonical_id"], selectedId ?? ""],
  ]);
  map.setFilter("selection-point", selectedFilter("point", selectedId));
};

export function MapView({
  visibleLayerIds,
  districtIds,
  navigationRequest,
  selectedFeatureId,
  onFeatureSelect,
  onVisibleFeatureIdsChange,
  onRequestStateChange,
  onZoomChange,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const visibleLayerIdsRef = useRef(visibleLayerIds);
  const districtIdsRef = useRef(districtIds);
  const selectedFeatureIdRef = useRef(selectedFeatureId);
  const onFeatureSelectRef = useRef(onFeatureSelect);
  const onVisibleFeatureIdsChangeRef = useRef(onVisibleFeatureIdsChange);
  const onRequestStateChangeRef = useRef(onRequestStateChange);
  const onZoomChangeRef = useRef(onZoomChange);
  const latestDataRef = useRef<CatalogFeatureCollection>(EMPTY_FEATURE_COLLECTION);
  const requestRef = useRef(new LatestMapRequest());
  const debounceTimerRef = useRef<number | null>(null);
  const loadViewportRef = useRef<(delay?: number) => void>(() => undefined);

  visibleLayerIdsRef.current = visibleLayerIds;
  districtIdsRef.current = districtIds;
  selectedFeatureIdRef.current = selectedFeatureId;
  onFeatureSelectRef.current = onFeatureSelect;
  onVisibleFeatureIdsChangeRef.current = onVisibleFeatureIdsChange;
  onRequestStateChangeRef.current = onRequestStateChange;
  onZoomChangeRef.current = onZoomChange;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    maplibregl.setWorkerUrl(maplibreWorkerUrl);
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: primaryStyleUrl || localDarkStyle,
      center: INITIAL_CENTER,
      zoom: INITIAL_ZOOM,
      attributionControl: {
        compact: true,
        ...(basemapAttribution ? { customAttribution: basemapAttribution } : {}),
      },
      renderWorldCopies: false,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");

    let resizeFrame: number | null = null;
    const resizeMap = (): void => {
      if (resizeFrame !== null) window.cancelAnimationFrame(resizeFrame);
      resizeFrame = window.requestAnimationFrame(() => {
        resizeFrame = null;
        map.resize();
      });
    };
    const resizeObserver =
      typeof ResizeObserver === "undefined" ? null : new ResizeObserver(resizeMap);
    resizeObserver?.observe(containerRef.current);
    resizeMap();

    const setSourceData = (collection: CatalogFeatureCollection): void => {
      const source = map.getSource(SOURCE_ID) as GeoJSONSource | undefined;
      if (source) source.setData(collection as Parameters<GeoJSONSource["setData"]>[0]);
    };

    const loadViewport = (delay = VIEWPORT_DEBOUNCE_MS): void => {
      if (debounceTimerRef.current !== null) window.clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = window.setTimeout(() => {
        if (!map.getSource(SOURCE_ID)) return;
        const bounds = map.getBounds();
        const requestBounds = {
          minLon: bounds.getWest(),
          minLat: bounds.getSouth(),
          maxLon: bounds.getEast(),
          maxLat: bounds.getNorth(),
        };
        const bboxGuard = guardBbox(requestBounds);
        if (!bboxGuard.valid) {
          requestRef.current.cancel();
          onRequestStateChangeRef.current({ status: "bbox-too-large" });
          return;
        }

        const categories = activeCategoryKeys(visibleLayerIdsRef.current, map.getZoom());
        if (categories.length === 0) {
          requestRef.current.cancel();
          latestDataRef.current = EMPTY_FEATURE_COLLECTION;
          setSourceData(EMPTY_FEATURE_COLLECTION);
          onRequestStateChangeRef.current({ status: "empty", durationMs: 0 });
          return;
        }

        const startedAt = performance.now();
        onRequestStateChangeRef.current({ status: "loading" });
        void requestRef.current.run(
          {
            bounds: requestBounds,
            categories,
            districtIds: [...districtIdsRef.current],
            limit: 5000,
          },
          (collection) => {
            latestDataRef.current = collection;
            setSourceData(collection);
            onVisibleFeatureIdsChangeRef.current(
              new Set(collection.features.map((feature) => feature.properties.canonical_id)),
            );
            const durationMs = performance.now() - startedAt;
            onRequestStateChangeRef.current(
              collection.features.length === 0
                ? { status: "empty", durationMs }
                : { status: "ready", featureCount: collection.features.length, durationMs },
            );
          },
          (error) => {
            if (error instanceof MapApiError && error.code === "feature_limit_exceeded") {
              onRequestStateChangeRef.current({ status: "feature-limit" });
              return;
            }
            onRequestStateChangeRef.current({
              status: "error",
              message: "Не удалось загрузить объекты. Переместите карту, чтобы повторить.",
            });
          },
        );
      }, delay);
    };
    loadViewportRef.current = loadViewport;

    const installOverlay = (): void => {
      installCatalogLayers(
        map,
        latestDataRef.current,
        visibleLayerIdsRef.current,
        selectedFeatureIdRef.current,
      );
      loadViewport(0);
    };

    let localFallbackApplied = false;
    let primaryStyleLoaded = false;
    map.on("style.load", installOverlay);
    map.on("load", () => {
      primaryStyleLoaded = true;
    });
    map.on("error", (event) => {
      if (primaryStyleUrl && !localFallbackApplied && !primaryStyleLoaded) {
        localFallbackApplied = true;
        map.setStyle(localDarkStyle);
        return;
      }
      console.error("MapLibre runtime error", event.error ?? event);
    });
    map.on("moveend", () => {
      onZoomChangeRef.current(map.getZoom());
      loadViewport();
    });
    map.on("mousemove", (event: maplibregl.MapMouseEvent) => {
      const layers = interactiveRenderLayerIds.filter((id) => map.getLayer(id));
      const interactive =
        layers.length > 0 && map.queryRenderedFeatures(event.point, { layers }).length > 0;
      map.getCanvas().style.cursor = interactive ? "pointer" : "";
    });
    map.on("click", (event: maplibregl.MapMouseEvent) => {
      const layers = interactiveRenderLayerIds.filter((id) => map.getLayer(id));
      if (layers.length === 0) return;
      const feature = map.queryRenderedFeatures(event.point, { layers })[0];
      const canonicalId = feature?.properties?.canonical_id;
      if (typeof canonicalId === "string") {
        onFeatureSelectRef.current(canonicalId);
      }
    });

    const request = requestRef.current;
    return () => {
      if (debounceTimerRef.current !== null) window.clearTimeout(debounceTimerRef.current);
      if (resizeFrame !== null) window.cancelAnimationFrame(resizeFrame);
      resizeObserver?.disconnect();
      request.cancel();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getSource(SOURCE_ID)) return;
    for (const logicalLayer of layerRegistry) {
      const visibility = visibleLayerIds.has(logicalLayer.id) ? "visible" : "none";
      for (const definition of logicalLayer.renderDefinitions) {
        if (map.getLayer(definition.id)) {
          map.setLayoutProperty(definition.id, "visibility", visibility);
        }
      }
    }
    loadViewportRef.current(0);
  }, [visibleLayerIds]);

  useEffect(() => {
    loadViewportRef.current(0);
  }, [districtIds]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || navigationRequest === null) return;
    const [minLon, minLat, maxLon, maxLat] = navigationRequest.bbox;
    map.fitBounds(
      [
        [minLon, minLat],
        [maxLon, maxLat],
      ],
      { padding: 48, duration: 700 },
    );
  }, [navigationRequest]);

  useEffect(() => {
    const map = mapRef.current;
    if (map) updateSelectionFilters(map, selectedFeatureId);
  }, [selectedFeatureId]);

  return <div ref={containerRef} className="catalog-map" aria-label="Карта Санкт-Петербурга" />;
}
