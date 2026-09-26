import type { District } from "../api/districts";
import { DistrictSection, type DistrictLoadState } from "./DistrictSection";
import { LayerControl } from "./LayerControl";
import { StatusIndicator } from "./StatusIndicator";

type ConnectionState = "checking" | "ready" | "offline";

export type SidebarProps = {
  expanded: boolean;
  backend: ConnectionState;
  postgis: ConnectionState;
  districtState: DistrictLoadState;
  selectedDistrictIds: ReadonlySet<string>;
  visibleLayerIds: ReadonlySet<string>;
  zoom: number;
  onExpandedChange: (expanded: boolean) => void;
  onDistrictToggle: (districtId: string) => void;
  onDistrictClear: () => void;
  onDistrictLocate: (district: District) => void;
  onDistrictLocateSelected: () => void;
  onDistrictRetry: () => void;
  onLayerToggle: (layerId: string) => void;
};

export function Sidebar({
  expanded,
  backend,
  postgis,
  districtState,
  selectedDistrictIds,
  visibleLayerIds,
  zoom,
  onExpandedChange,
  onDistrictToggle,
  onDistrictClear,
  onDistrictLocate,
  onDistrictLocateSelected,
  onDistrictRetry,
  onLayerToggle,
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

      {expanded && (
        <div
          className="sidebar__content"
          role="region"
          aria-label="Прокручиваемые настройки карты"
          tabIndex={0}
        >
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
            onToggle={onLayerToggle}
          />

          <section className="system-status" aria-label="Состояние системы">
            <p className="section-label">System</p>
            <StatusIndicator label="Backend" status={backend} />
            <StatusIndicator label="PostGIS" status={postgis} />
          </section>
        </div>
      )}
    </aside>
  );
}
