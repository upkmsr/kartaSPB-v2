import type { District } from "../api/districts";
import { DistrictSection, type DistrictLoadState } from "./DistrictSection";
import { LayerControl } from "./LayerControl";
import { SearchSection } from "./SearchSection";
import { StatusIndicator } from "./StatusIndicator";
import type { SearchResult } from "../api/search";
import type { MapRequestState } from "../map/mapTypes";

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
