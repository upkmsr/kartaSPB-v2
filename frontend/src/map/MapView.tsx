import { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import type {
  Map as MapLibreMap,
  StyleSpecification,
} from "maplibre-gl";
import {
  EMPTY_DISTRICT_GEOMETRY,
  LatestDistrictGeometryRequest,
  type DistrictGeometryFeatureCollection,
} from "../api/districts";
import {
  interactionIndex,
  interactiveRenderLayerIds,
  layerRegistry,
  orderedRenderDefinitions,
} from "./layerRegistry";
import type { MapSelection } from "./layerContract";
import { resolveMapSelection } from "./layerRegistryHelpers";
import {
  CATALOG_SOURCE_ID,
  planCatalogViewport,
  setCatalogSourceData,
  updateCatalogSelection,
} from "./catalogLayerDriver";
import { installRegisteredLayers, setRegisteredLayerVisibility } from "./layerRuntime";
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
  onSelection: (selection: MapSelection) => void;
  onVisibleFeatureIdsChange: (visibleIds: ReadonlySet<string>) => void;
  onRequestStateChange: (state: MapRequestState) => void;
  onZoomChange: (zoom: number) => void;
};

export function MapView({
  visibleLayerIds,
  autoLoad = true,
  manualLoadSequence = 0,
  districtIds,
  navigationRequest,
  selectedFeatureId,
  onSelection,
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
  const onSelectionRef = useRef<(selection: MapSelection) => void>(() => undefined);
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
  onSelectionRef.current = onSelection;
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

    const clearCatalog = (state: MapRequestState): void => {
      requestRef.current.cancel();
      inFlightSignatureRef.current = null;
      successfulSignatureRef.current = null;
      latestSuccessfulStateRef.current = null;
      latestDataRef.current = EMPTY_FEATURE_COLLECTION;
      setCatalogSourceData(map, EMPTY_FEATURE_COLLECTION);
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
        if (!map.getSource(CATALOG_SOURCE_ID)) return;
        const zoom = map.getZoom();
        const catalogPlan = planCatalogViewport(layerRegistry, visibleLayerIdsRef.current, zoom);
        if (catalogPlan.enabledLayerIds.length === 0) {
          clearCatalog({ status: "no-enabled-layers" });
          return;
        }

        const loadableLayerIds = catalogPlan.loadableLayerIds;
        if (loadableLayerIds.length === 0) {
          clearCatalog({
            status: "waiting-for-zoom",
            waitingLayerIds: catalogPlan.enabledLayerIds,
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

        const categories = catalogPlan.categoryKeys;
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
            setCatalogSourceData(map, collection);
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
      installRegisteredLayers(
        map,
        layerRegistry,
        visibleLayerIdsRef.current,
        {
          catalogData: latestDataRef.current,
          selectedCanonicalId: selectedFeatureIdRef.current,
        },
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
      if (!feature) return;
      const selection = resolveMapSelection(feature.layer?.id ?? layers[0], feature, interactionIndex);
      if (selection) onSelectionRef.current(selection);
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
    if (!map || !map.getSource(CATALOG_SOURCE_ID)) return;
    setRegisteredLayerVisibility(map, layerRegistry, visibleLayerIds);
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
    if (map) updateCatalogSelection(map, selectedFeatureId);
  }, [selectedFeatureId]);

  return <div ref={containerRef} className="catalog-map" aria-label="Карта Санкт-Петербурга" />;
}
