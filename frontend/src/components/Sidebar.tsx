import type { District } from "../api/districts";
import { DistrictSection, type DistrictLoadState } from "./DistrictSection";
import { LayerControl } from "./LayerControl";
import { MapSettingsPanel } from "./MapSettingsPanel";
import { SearchSection } from "./SearchSection";
import { StatusIndicator } from "./StatusIndicator";
import type { SearchResult } from "../api/search";
import type { MapRequestState } from "../map/mapTypes";
import type { PreparedHeatmap } from "../api/heatmap";
import { ScenarioBuilder } from "./ScenarioBuilder";
import { IndependentLayers } from "./IndependentLayers";
import type { AnalysisMode } from "../analysis/analysisPreferences";
import type { IndependentLayerState } from "../analysis/analysisPreferences";
import type { PreparedInfluence } from "../api/influence";
import { useState } from "react";
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
  heatmapInspectionEnabled: boolean;
  activeAnalysisMode: AnalysisMode;
  scenarioWeights: Record<string, number>;
  scenarioMinScore: number;
  influenceLayers: Record<string, IndependentLayerState>;
  preparedInfluence: PreparedInfluence | null;
  accentedFactorId: string | null;
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
  onHeatmapDisplayRangeChange?: (range: HeatmapDisplayRange) => void;
  onHeatmapHide: () => void;
  onHeatmapInspectionEnabledChange: (enabled: boolean) => void;
  onActiveAnalysisModeChange: (mode: AnalysisMode) => void;
  onScenarioWeightsChange: (weights: Record<string, number>) => void;
  onScenarioMinScoreChange: (minimumScore: number) => void;
  onInfluenceLayersChange: (layers: Record<string, IndependentLayerState>) => void;
  onInfluencePrepared: (prepared: PreparedInfluence) => void;
  onInfluenceHide: () => void;
  onInfluenceAccentChange: (factorId: string | null) => void;
  onObjectLayerVisibilityChange: (layerId: string, visible: boolean) => void;
};

type SidebarTab = "influence" | "composite" | "objects" | "territories" | "settings";

const tabs: readonly { id: SidebarTab; label: string; shortLabel: string }[] = [
  { id: "influence", label: "Слои влияния", shortLabel: "Влияние" },
  { id: "composite", label: "Общий анализ", shortLabel: "Анализ" },
  { id: "objects", label: "Объекты на карте", shortLabel: "Объекты" },
  { id: "territories", label: "Территории", shortLabel: "Районы" },
  { id: "settings", label: "Настройки карты", shortLabel: "Настройки" },
];

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
  heatmapInspectionEnabled,
  activeAnalysisMode,
  scenarioWeights,
  scenarioMinScore,
  influenceLayers,
  preparedInfluence,
  accentedFactorId,
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
  onHeatmapDisplayRangeChange = () => undefined,
  onHeatmapHide,
  onHeatmapInspectionEnabledChange,
  onActiveAnalysisModeChange,
  onScenarioWeightsChange,
  onScenarioMinScoreChange,
  onInfluenceLayersChange,
  onInfluencePrepared,
  onInfluenceHide,
  onInfluenceAccentChange,
  onObjectLayerVisibilityChange,
}: SidebarProps) {
  const [activeTab, setActiveTab] = useState<SidebarTab>(
    activeAnalysisMode === "composite" ? "composite" : "influence",
  );
  const selectTab = (tab: SidebarTab): void => {
    setActiveTab(tab);
    if (tab === "influence") onActiveAnalysisModeChange("independent");
    if (tab === "composite") onActiveAnalysisModeChange("composite");
  };
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
          <nav className="sidebar-tabs" role="tablist" aria-label="Разделы карты">
            {tabs.map((tab) => (
              <button
                type="button"
                role="tab"
                aria-label={tab.label}
                aria-selected={activeTab === tab.id}
                aria-controls={`sidebar-panel-${tab.id}`}
                id={`sidebar-tab-${tab.id}`}
                key={tab.id}
                onClick={() => selectTab(tab.id)}
              >
                <span>{tab.shortLabel}</span>
              </button>
            ))}
          </nav>

          <div className="sidebar-panels">
            <section
              id="sidebar-panel-influence"
              role="tabpanel"
              aria-labelledby="sidebar-tab-influence"
              hidden={activeTab !== "influence"}
            >
              <IndependentLayers
                active={activeAnalysisMode === "independent"}
                zoom={zoom}
                layers={influenceLayers}
                prepared={preparedInfluence}
                accentedFactorId={accentedFactorId}
                tileError={activeAnalysisMode === "independent" ? heatmapTileError : null}
                onLayersChange={onInfluenceLayersChange}
                onPrepared={onInfluencePrepared}
                onHide={onInfluenceHide}
                onAccentChange={onInfluenceAccentChange}
                onObjectLayerVisibilityChange={onObjectLayerVisibilityChange}
              />
            </section>
            <section
              id="sidebar-panel-composite"
              role="tabpanel"
              aria-labelledby="sidebar-tab-composite"
              hidden={activeTab !== "composite"}
            >
              <ScenarioBuilder
                active={heatmapOwner === "scenario"}
                activeHeatmap={heatmapOwner === "scenario" ? activeHeatmap : null}
                zoom={zoom}
                tileError={heatmapOwner === "scenario" ? heatmapTileError : null}
                inspectEnabled={heatmapInspectionEnabled}
                displayRange={heatmapDisplayRange}
                weights={scenarioWeights}
                minimumScore={scenarioMinScore}
                onWeightsChange={onScenarioWeightsChange}
                onMinimumScoreChange={onScenarioMinScoreChange}
                onPrepared={onScenarioPrepared}
                onDisplayRangeChange={onHeatmapDisplayRangeChange}
                onHide={onHeatmapHide}
                onInspectEnabledChange={onHeatmapInspectionEnabledChange}
              />
            </section>
            <section
              id="sidebar-panel-objects"
              role="tabpanel"
              aria-labelledby="sidebar-tab-objects"
              hidden={activeTab !== "objects"}
            >
              <LayerControl
                visibleLayerIds={visibleLayerIds}
                zoom={zoom}
                requestState={mapRequestState}
                onToggle={onLayerToggle}
              />
            </section>
            <section
              id="sidebar-panel-territories"
              role="tabpanel"
              aria-labelledby="sidebar-tab-territories"
              hidden={activeTab !== "territories"}
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
            </section>
            <section
              id="sidebar-panel-settings"
              role="tabpanel"
              aria-labelledby="sidebar-tab-settings"
              hidden={activeTab !== "settings"}
            >
              <MapSettingsPanel
                autoLoad={autoLoad}
                requestState={mapRequestState}
                onAutoLoadChange={onAutoLoadChange}
                onLoadObjects={onLoadObjects}
                onReset={onResetLoadingSettings}
              />
              <section className="system-status" aria-label="Состояние системы">
                <p className="section-label">System</p>
                <StatusIndicator label="Backend" status={backend} />
                <StatusIndicator label="PostGIS" status={postgis} />
              </section>
            </section>
          </div>
      </div>
    </aside>
  );
}
