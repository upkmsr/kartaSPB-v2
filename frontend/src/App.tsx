import { useEffect, useMemo, useRef, useState } from "react";
import {
  combinedDistrictBbox,
  fetchDistricts,
  type District,
  type DistrictBbox,
} from "./api/districts";
import { fetchReadiness } from "./api/health";
import type { SearchResult } from "./api/search";
import type { DistrictLoadState } from "./components/DistrictSection";
import { MapWorkspace } from "./components/MapWorkspace";
import { Sidebar } from "./components/Sidebar";
import { defaultVisibleLayerIds, enabledCategoryKeys } from "./map/layerRegistry";
import { searchResultNavigation } from "./map/searchNavigation";
import type { MapNavigationRequest, MapNavigationTarget } from "./map/mapTypes";

type ConnectionState = "checking" | "ready" | "offline";
const INITIAL_ZOOM = 12;

type ObjectSelection = { id: string; origin: "map" | "search" };

export function App() {
  const [backend, setBackend] = useState<ConnectionState>("checking");
  const [postgis, setPostgis] = useState<ConnectionState>("checking");
  const [zoom, setZoom] = useState(INITIAL_ZOOM);
  const [visibleLayerIds, setVisibleLayerIds] = useState(defaultVisibleLayerIds);
  const [sidebarExpanded, setSidebarExpanded] = useState(true);
  const [districtState, setDistrictState] = useState<DistrictLoadState>({
    status: "loading",
  });
  const [districtRetry, setDistrictRetry] = useState(0);
  const [selectedDistrictIds, setSelectedDistrictIds] = useState<Set<string>>(new Set());
  const [navigationRequest, setNavigationRequest] = useState<MapNavigationRequest | null>(null);
  const [objectSelection, setObjectSelection] = useState<ObjectSelection | null>(null);
  const navigationSequenceRef = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    fetchReadiness(controller.signal)
      .then((report) => {
        setBackend(report.status === "ready" ? "ready" : "offline");
        setPostgis(report.postgis.status === "ready" ? "ready" : "offline");
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setBackend("offline");
          setPostgis("offline");
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setDistrictState({ status: "loading" });
    fetchDistricts(controller.signal)
      .then((districts) => {
        if (!controller.signal.aborted) setDistrictState({ status: "loaded", districts });
      })
      .catch(() => {
        if (!controller.signal.aborted) setDistrictState({ status: "error" });
      });
    return () => controller.abort();
  }, [districtRetry]);

  const toggleLayer = (layerId: string) => {
    setVisibleLayerIds((current) => {
      const next = new Set(current);
      if (next.has(layerId)) next.delete(layerId);
      else next.add(layerId);
      return next;
    });
  };

  const toggleDistrict = (districtId: string) => {
    setSelectedDistrictIds((current) => {
      const next = new Set(current);
      if (next.has(districtId)) next.delete(districtId);
      else next.add(districtId);
      return next;
    });
  };

  const navigate = (target: MapNavigationTarget) => {
    setNavigationRequest({ sequence: ++navigationSequenceRef.current, ...target });
  };

  const navigateToBbox = (bbox: DistrictBbox) => {
    navigate({ kind: "bbox", bbox });
  };

  const selectedDistricts = useMemo(() => {
    if (districtState.status !== "loaded") return [];
    return districtState.districts.filter((district) => selectedDistrictIds.has(district.id));
  }, [districtState, selectedDistrictIds]);

  const districtIds = useMemo(() => [...selectedDistrictIds], [selectedDistrictIds]);
  const searchCategoryKeys = useMemo(
    () => enabledCategoryKeys(visibleLayerIds),
    [visibleLayerIds],
  );

  const navigateToSelected = () => {
    const bbox = combinedDistrictBbox(selectedDistricts);
    if (bbox) navigateToBbox(bbox);
  };

  const activateSearchResult = (result: SearchResult) => {
    setObjectSelection({ id: result.id, origin: "search" });
    navigate(searchResultNavigation(result));
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            К
          </span>
          <div>
            <h1>KARTASPB</h1>
            <p>Data-driven GIS platform</p>
          </div>
        </div>
        <div className="topbar-meta">
          <span>59°57′ N</span>
          <span>30°19′ E</span>
          <span className="version">FOUNDATION 5</span>
        </div>
      </header>

      <div className={sidebarExpanded ? "workspace" : "workspace workspace--collapsed"}>
        <Sidebar
          expanded={sidebarExpanded}
          backend={backend}
          postgis={postgis}
          districtState={districtState}
          selectedDistrictIds={selectedDistrictIds}
          districtIds={districtIds}
          visibleLayerIds={visibleLayerIds}
          searchCategoryKeys={searchCategoryKeys}
          selectedObjectId={objectSelection?.id ?? null}
          zoom={zoom}
          onExpandedChange={setSidebarExpanded}
          onDistrictToggle={toggleDistrict}
          onDistrictClear={() => setSelectedDistrictIds(new Set())}
          onDistrictLocate={(district: District) => navigateToBbox(district.bbox)}
          onDistrictLocateSelected={navigateToSelected}
          onDistrictRetry={() => setDistrictRetry((value) => value + 1)}
          onLayerToggle={toggleLayer}
          onSearchResultActivate={activateSearchResult}
        />

        <MapWorkspace
          visibleLayerIds={visibleLayerIds}
          districtIds={districtIds}
          navigationRequest={navigationRequest}
          objectSelection={objectSelection}
          onObjectSelect={(id) => setObjectSelection({ id, origin: "map" })}
          onObjectClose={() => setObjectSelection(null)}
          onZoomChange={setZoom}
        />
      </div>

      <div className="viewport-warning" role="alert">
        <strong>KARTASPB — desktop GIS</strong>
        <span>Для работы рекомендуется экран шириной от 1280 px.</span>
      </div>
    </div>
  );
}
