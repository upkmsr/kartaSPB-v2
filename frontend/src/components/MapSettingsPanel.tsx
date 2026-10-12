import type { MapRequestState } from "../map/mapTypes";
import type { HeatmapResolutionMode } from "../map/heatmapResolution";
import type { MapPerformanceProfile } from "../map/performanceProfile";

type MapSettingsPanelProps = {
  autoLoad: boolean;
  requestState: MapRequestState;
  onAutoLoadChange: (autoLoad: boolean) => void;
  onLoadObjects: () => void;
  onReset: () => void;
  performanceProfile?: MapPerformanceProfile;
  analysisDetail?: HeatmapResolutionMode;
  onPerformanceProfileChange?: (profile: MapPerformanceProfile) => void;
  onAnalysisDetailChange?: (detail: HeatmapResolutionMode) => void;
};

export function MapSettingsPanel({
  autoLoad,
  requestState,
  onAutoLoadChange,
  onLoadObjects,
  onReset,
  performanceProfile = "balanced",
  analysisDetail = "auto",
  onPerformanceProfileChange = () => undefined,
  onAnalysisDetailChange = () => undefined,
}: MapSettingsPanelProps) {
  const manualLoadPending = requestState.status === "pending-manual-load";
  return (
    <section aria-labelledby="map-settings-heading">
      <p className="section-label" id="map-settings-heading">Загрузка карты</p>
      <div className="layer-loading-settings" aria-label="Настройки загрузки объектов">
        <fieldset className="map-performance-presets">
          <legend>Производительность</legend>
          {([[
            "economy", "Экономичный",
          ], ["balanced", "Сбалансированный"], ["detailed", "Подробный"]] as const).map(([id, label]) => (
            <button
              type="button"
              key={id}
              aria-pressed={performanceProfile === id}
              onClick={() => onPerformanceProfileChange(id)}
            >
              {label}
            </button>
          ))}
        </fieldset>
        <fieldset className="map-performance-presets">
          <legend>Детализация аналитики</legend>
          {([[
            "auto", "Авто",
          ], ["200m", "200 м"], ["50m", "50 м"]] as const).map(([id, label]) => (
            <button
              type="button"
              key={id}
              aria-pressed={analysisDetail === id}
              onClick={() => onAnalysisDetailChange(id)}
            >
              {label}
            </button>
          ))}
          <small>50 м применяются с z13; обзор города всегда использует экономичную агрегацию.</small>
        </fieldset>
        <label className="layer-loading-settings__auto">
          <input
            type="checkbox"
            checked={autoLoad}
            onChange={(event) => onAutoLoadChange(event.target.checked)}
          />
          <span>Автоматически загружать объекты</span>
        </label>
        {!autoLoad && (
          <button
            type="button"
            className="layer-loading-settings__load"
            disabled={!manualLoadPending}
            onClick={onLoadObjects}
          >
            Загрузить объекты
          </button>
        )}
        {!autoLoad && manualLoadPending && (
          <small role="status">Карта изменена — загрузите объекты</small>
        )}
        <button type="button" className="layer-loading-settings__reset" onClick={onReset}>
          Сбросить настройки
        </button>
      </div>
    </section>
  );
}
