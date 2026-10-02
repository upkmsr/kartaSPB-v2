import { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import type {
  ExpressionSpecification,
  FilterSpecification,
  GeoJSONSource,
  Map as MapLibreMap,
  StyleSpecification,
} from "maplibre-gl";
import {
  EMPTY_DISTRICT_GEOMETRY,
  LatestDistrictGeometryRequest,
  type DistrictGeometryFeatureCollection,
} from "../api/districts";
import {
  activeCategoryKeys,
  categoryFilter,
  geometryFilter,
  interactiveRenderLayerIds,
  layerRegistry,
  orderedRenderDefinitions,
} from "./layerRegistry";
import { alignOpenFreeMapRoadArrows } from "./basemapStyle";
import {
  installSelectedDistrictOverlay,
  setSelectedDistrictOverlayData,
} from "./districtOverlay";
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
  autoLoad?: boolean;
  manualLoadSequence?: number;
  districtIds: readonly string[];
  navigationRequest: MapNavigationRequest | null;
  selectedFeatureId: string | null;
  onFeatureSelect: (objectId: string) => void;
  onVisibleFeatureIdsChange: (visibleIds: ReadonlySet<string>) => void;
  onRequestStateChange: (state: MapRequestState) => void;
  onZoomChange: (zoom: number) => void;
};

const selectedMembershipFilter = (selectedId: string | null): ExpressionSpecification => [
  "any",
  ["==", ["get", "canonical_id"], selectedId ?? ""],
  ["in", selectedId ?? "", ["get", "member_canonical_ids"]],
];

const selectedFilter = (
  geometry: "point" | "line" | "polygon",
  selectedId: string | null,
): FilterSpecification => [
  "all",
  geometryFilter(geometry),
  selectedMembershipFilter(selectedId),
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
        selectedMembershipFilter(selectedId),
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
    selectedMembershipFilter(selectedId),
  ]);
  map.setFilter("selection-point", selectedFilter("point", selectedId));
};

export function MapView({
  visibleLayerIds,
  autoLoad = true,
  manualLoadSequence = 0,
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
  const autoLoadRef = useRef(autoLoad);
  const districtIdsRef = useRef(districtIds);
  const selectedFeatureIdRef = useRef(selectedFeatureId);
  const onFeatureSelectRef = useRef(onFeatureSelect);
  const onVisibleFeatureIdsChangeRef = useRef(onVisibleFeatureIdsChange);
  const onRequestStateChangeRef = useRef(onRequestStateChange);
  const onZoomChangeRef = useRef(onZoomChange);
  const latestDataRef = useRef<CatalogFeatureCollection>(EMPTY_FEATURE_COLLECTION);
  const latestSuccessfulStateRef = useRef<
    Extract<MapRequestState, { status: "ready" | "empty" }> | null
  >(null);
  const successfulSignatureRef = useRef<string | null>(null);
  const inFlightSignatureRef = useRef<string | null>(null);
  const latestDistrictDataRef = useRef<DistrictGeometryFeatureCollection>(
    EMPTY_DISTRICT_GEOMETRY,
  );
  const requestRef = useRef(new LatestMapRequest());
  const districtGeometryRequestRef = useRef(new LatestDistrictGeometryRequest());
  const debounceTimerRef = useRef<number | null>(null);
  const loadViewportRef = useRef<(delay?: number, force?: boolean) => void>(() => undefined);

  visibleLayerIdsRef.current = visibleLayerIds;
  autoLoadRef.current = autoLoad;
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

    const clearCatalog = (state: MapRequestState): void => {
      requestRef.current.cancel();
      inFlightSignatureRef.current = null;
      successfulSignatureRef.current = null;
      latestSuccessfulStateRef.current = null;
      latestDataRef.current = EMPTY_FEATURE_COLLECTION;
      setSourceData(EMPTY_FEATURE_COLLECTION);
      onVisibleFeatureIdsChangeRef.current(new Set());
      onRequestStateChangeRef.current(state);
    };

    const reportLoadedState = (): void => {
      if (latestSuccessfulStateRef.current) {
        onRequestStateChangeRef.current(latestSuccessfulStateRef.current);
      }
    };

    const loadViewport = (delay = VIEWPORT_DEBOUNCE_MS, force = false): void => {
      if (debounceTimerRef.current !== null) window.clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = window.setTimeout(() => {
        if (!map.getSource(SOURCE_ID)) return;
        const enabledLayers = layerRegistry.filter((layer) =>
          visibleLayerIdsRef.current.has(layer.id),
        );
        if (enabledLayers.length === 0) {
          clearCatalog({ status: "no-enabled-layers" });
          return;
        }

        const zoom = map.getZoom();
        const loadableLayerIds = enabledLayers
          .filter((layer) => zoom >= layer.minZoom)
          .map((layer) => layer.id);
        if (loadableLayerIds.length === 0) {
          clearCatalog({
            status: "waiting-for-zoom",
            waitingLayerIds: enabledLayers.map((layer) => layer.id),
          });
          return;
        }

        const bounds = map.getBounds();
        const requestBounds = {
          minLon: bounds.getWest(),
          minLat: bounds.getSouth(),
          maxLon: bounds.getEast(),
          maxLat: bounds.getNorth(),
        };
        const bboxGuard = guardBbox(requestBounds);
        if (!bboxGuard.valid) {
          clearCatalog({ status: "bbox-too-large" });
          return;
        }

        const categories = activeCategoryKeys(visibleLayerIdsRef.current, map.getZoom());
        const signature = JSON.stringify({
          bbox: bboxGuard.bbox,
          categories: [...categories].sort(),
          districts: [...districtIdsRef.current].sort(),
        });
        if (!force && successfulSignatureRef.current === signature) {
          reportLoadedState();
          return;
        }
        if (!force && !autoLoadRef.current) {
          requestRef.current.cancel();
          inFlightSignatureRef.current = null;
          onRequestStateChangeRef.current({ status: "pending-manual-load", loadableLayerIds });
          return;
        }
        if (!force && inFlightSignatureRef.current === signature) {
          return;
        }

        const startedAt = performance.now();
        inFlightSignatureRef.current = signature;
        onRequestStateChangeRef.current({ status: "loading", loadableLayerIds });
        void requestRef.current.run(
          {
            bounds: requestBounds,
            categories,
            districtIds: [...districtIdsRef.current],
            limit: 5000,
          },
          (collection) => {
            inFlightSignatureRef.current = null;
            successfulSignatureRef.current = signature;
            latestDataRef.current = collection;
            setSourceData(collection);
            onVisibleFeatureIdsChangeRef.current(
              new Set(
                collection.features.flatMap(
                  (feature) =>
                    feature.properties.member_canonical_ids ?? [feature.properties.canonical_id],
                ),
              ),
            );
            const durationMs = performance.now() - startedAt;
            const completedState: Extract<
              MapRequestState,
              { status: "ready" | "empty" }
            > =
              collection.features.length === 0
                ? { status: "empty", durationMs, loadedLayerIds: loadableLayerIds }
                : {
                    status: "ready",
                    featureCount: collection.features.length,
                    durationMs,
                    loadedLayerIds: loadableLayerIds,
                  };
            latestSuccessfulStateRef.current = completedState;
            onRequestStateChangeRef.current(completedState);
          },
          (error) => {
            inFlightSignatureRef.current = null;
            if (error instanceof MapApiError && error.code === "feature_limit_exceeded") {
              clearCatalog({ status: "feature-limit" });
              return;
            }
            if (latestDataRef.current.features.length > 0) {
              onRequestStateChangeRef.current({
                status: "stale-error",
                message: "Не удалось обновить объекты — показаны предыдущие данные",
              });
            } else {
              clearCatalog({
                status: "error",
                message: "Не удалось загрузить объекты. Переместите карту, чтобы повторить.",
              });
            }
          },
        );
      }, delay);
    };
    loadViewportRef.current = loadViewport;

    const installOverlay = (): void => {
      if (primaryStyleUrl === DEFAULT_STYLE_URL) alignOpenFreeMapRoadArrows(map);
      installCatalogLayers(
        map,
        latestDataRef.current,
        visibleLayerIdsRef.current,
        selectedFeatureIdRef.current,
      );
      installSelectedDistrictOverlay(
        map,
        latestDistrictDataRef.current,
        orderedRenderDefinitions[0]?.definition.id,
        "selection-fill",
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
      const canonicalId =
        feature?.properties?.representative_canonical_id ?? feature?.properties?.canonical_id;
      if (typeof canonicalId === "string") {
        onFeatureSelectRef.current(canonicalId);
      }
    });

    const request = requestRef.current;
    const districtGeometryRequest = districtGeometryRequestRef.current;
    return () => {
      if (debounceTimerRef.current !== null) window.clearTimeout(debounceTimerRef.current);
      if (resizeFrame !== null) window.cancelAnimationFrame(resizeFrame);
      resizeObserver?.disconnect();
      request.cancel();
      districtGeometryRequest.cancel();
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
  }, [autoLoad]);

  useEffect(() => {
    if (manualLoadSequence > 0) loadViewportRef.current(0, true);
  }, [manualLoadSequence]);

  useEffect(() => {
    loadViewportRef.current(0);
    const map = mapRef.current;
    const request = districtGeometryRequestRef.current;
    latestDistrictDataRef.current = EMPTY_DISTRICT_GEOMETRY;
    if (map) setSelectedDistrictOverlayData(map, EMPTY_DISTRICT_GEOMETRY);
    if (districtIds.length === 0) {
      request.cancel();
      return;
    }
    void request.run(
      districtIds,
      (collection) => {
        latestDistrictDataRef.current = collection;
        const currentMap = mapRef.current;
        if (currentMap) setSelectedDistrictOverlayData(currentMap, collection);
      },
      () => {
        // District filtering remains active even if its visual overlay cannot load.
      },
    );
  }, [districtIds]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || navigationRequest === null) return;
    if (navigationRequest.kind === "point") {
      map.flyTo({
        center: navigationRequest.center,
        zoom: navigationRequest.zoom,
        duration: 700,
      });
    } else {
      const [minLon, minLat, maxLon, maxLat] = navigationRequest.bbox;
      map.fitBounds(
        [
          [minLon, minLat],
          [maxLon, maxLat],
        ],
        { padding: 56, duration: 700, maxZoom: 17 },
      );
    }
  }, [navigationRequest]);

  useEffect(() => {
    const map = mapRef.current;
    if (map) updateSelectionFilters(map, selectedFeatureId);
  }, [selectedFeatureId]);

  return <div ref={containerRef} className="catalog-map" aria-label="Карта Санкт-Петербурга" />;
}
