import type { MapRequestState } from "../map/mapTypes";

type MapSettingsPanelProps = {
  autoLoad: boolean;
  requestState: MapRequestState;
  onAutoLoadChange: (autoLoad: boolean) => void;
  onLoadObjects: () => void;
  onReset: () => void;
};

export function MapSettingsPanel({
  autoLoad,
  requestState,
  onAutoLoadChange,
  onLoadObjects,
  onReset,
}: MapSettingsPanelProps) {
  const manualLoadPending = requestState.status === "pending-manual-load";
  return (
    <section aria-labelledby="map-settings-heading">
      <p className="section-label" id="map-settings-heading">Загрузка карты</p>
      <div className="layer-loading-settings" aria-label="Настройки загрузки объектов">
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
