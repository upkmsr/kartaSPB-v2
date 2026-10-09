import type { District } from "../api/districts";
import { DistrictSection, type DistrictLoadState } from "./DistrictSection";
import { LayerControl } from "./LayerControl";
import { SearchSection } from "./SearchSection";
import { StatusIndicator } from "./StatusIndicator";
import type { SearchResult } from "../api/search";
import type { MapRequestState } from "../map/mapTypes";
import type { PreparedHeatmap } from "../api/heatmap";
import { HeatmapControl } from "./HeatmapControl";
import { ScenarioBuilder } from "./ScenarioBuilder";
import {
  DEFAULT_HEATMAP_DISPLAY_RANGE,
  type HeatmapDisplayRange,
} from "../map/heatmapOverlay";

type ConnectionState = "checking" | "ready" | "offline";

export type SidebarProps = {
  expanded: boolean;
  backend: ConnectionState;
  postgis: ConnectionState;
  districtState: DistrictLoadState;
  selectedDistrictIds: ReadonlySet<string>;
  districtIds: readonly string[];
  visibleLayerIds: ReadonlySet<string>;
  autoLoad: boolean;
  mapRequestState: MapRequestState;
  searchCategoryKeys: readonly string[];
  selectedSearchResultId: string | null;
  activeHeatmap: PreparedHeatmap | null;
  heatmapOwner: "scenario" | "single" | null;
  heatmapDisplayRange?: HeatmapDisplayRange;
  heatmapTileError: string | null;
  zoom: number;
  onExpandedChange: (expanded: boolean) => void;
  onDistrictToggle: (districtId: string) => void;
  onDistrictClear: () => void;
  onDistrictLocate: (district: District) => void;
  onDistrictLocateSelected: () => void;
  onDistrictRetry: () => void;
  onLayerToggle: (layerId: string) => void;
  onAutoLoadChange: (autoLoad: boolean) => void;
  onLoadObjects: () => void;
  onResetLoadingSettings: () => void;
  onSearchResultActivate: (result: SearchResult) => void;
  onScenarioPrepared: (heatmap: PreparedHeatmap) => void;
  onSingleHeatmapPrepared: (heatmap: PreparedHeatmap) => void;
  onHeatmapDisplayRangeChange?: (range: HeatmapDisplayRange) => void;
  onHeatmapHide: () => void;
};

export function Sidebar({
  expanded,
  backend,
  postgis,
  districtState,
  selectedDistrictIds,
  districtIds,
  visibleLayerIds,
  autoLoad,
  mapRequestState,
  searchCategoryKeys,
  selectedSearchResultId,
  activeHeatmap,
  heatmapOwner,
  heatmapDisplayRange = DEFAULT_HEATMAP_DISPLAY_RANGE,
  heatmapTileError,
  zoom,
  onExpandedChange,
  onDistrictToggle,
  onDistrictClear,
  onDistrictLocate,
  onDistrictLocateSelected,
  onDistrictRetry,
  onLayerToggle,
  onAutoLoadChange,
  onLoadObjects,
  onResetLoadingSettings,
  onSearchResultActivate,
  onScenarioPrepared,
  onSingleHeatmapPrepared,
  onHeatmapDisplayRangeChange = () => undefined,
  onHeatmapHide,
}: SidebarProps) {
  return (
    <aside
      className={expanded ? "sidebar sidebar--expanded" : "sidebar sidebar--collapsed"}
      aria-label="Панель управления картой"
    >
      <button
        className="sidebar-toggle"
        type="button"
        onClick={() => onExpandedChange(!expanded)}
        aria-label={expanded ? "Свернуть панель" : "Развернуть панель"}
        aria-expanded={expanded}
      >
        <span aria-hidden="true">{expanded ? "‹" : "›"}</span>
        {expanded && <span>Свернуть</span>}
      </button>

      <div
        className="sidebar__content"
        role="region"
        aria-label="Прокручиваемые настройки карты"
        tabIndex={expanded ? 0 : -1}
        hidden={!expanded}
      >
          <SearchSection
            districtIds={districtIds}
            categoryKeys={searchCategoryKeys}
            selectedResultId={selectedSearchResultId}
            onResultActivate={onSearchResultActivate}
          />

          <DistrictSection
            state={districtState}
            selectedDistrictIds={selectedDistrictIds}
            onToggle={onDistrictToggle}
            onClear={onDistrictClear}
            onLocate={onDistrictLocate}
            onLocateSelected={onDistrictLocateSelected}
            onRetry={onDistrictRetry}
          />

          <ScenarioBuilder
            active={heatmapOwner === "scenario"}
            activeHeatmap={heatmapOwner === "scenario" ? activeHeatmap : null}
            districtIds={districtIds}
            zoom={zoom}
            tileError={heatmapOwner === "scenario" ? heatmapTileError : null}
            displayRange={heatmapDisplayRange}
            onPrepared={onScenarioPrepared}
            onDisplayRangeChange={onHeatmapDisplayRangeChange}
            onHide={onHeatmapHide}
          />

          <details className="single-metric-view">
            <summary>Один показатель</summary>
            <HeatmapControl
              activeHeatmap={heatmapOwner === "single" ? activeHeatmap : null}
              tileError={heatmapOwner === "single" ? heatmapTileError : null}
              displayRange={heatmapDisplayRange}
              zoom={zoom}
              onPrepared={onSingleHeatmapPrepared}
              onDisplayRangeChange={onHeatmapDisplayRangeChange}
              onHide={onHeatmapHide}
            />
          </details>

          <LayerControl
            visibleLayerIds={visibleLayerIds}
            zoom={zoom}
            autoLoad={autoLoad}
            requestState={mapRequestState}
            onToggle={onLayerToggle}
            onAutoLoadChange={onAutoLoadChange}
            onLoadObjects={onLoadObjects}
            onReset={onResetLoadingSettings}
          />

          <section className="system-status" aria-label="Состояние системы">
            <p className="section-label">System</p>
            <StatusIndicator label="Backend" status={backend} />
            <StatusIndicator label="PostGIS" status={postgis} />
          </section>
      </div>
    </aside>
  );
}
