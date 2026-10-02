import { layerRegistry } from "../map/layerRegistry";
import type { MapRequestState } from "../map/mapTypes";

export type LayerControlProps = {
  visibleLayerIds: ReadonlySet<string>;
  zoom: number;
  autoLoad: boolean;
  requestState: MapRequestState;
  onToggle: (layerId: string) => void;
  onAutoLoadChange: (autoLoad: boolean) => void;
  onLoadObjects: () => void;
  onReset: () => void;
};

const layerStatus = (
  layerId: string,
  enabled: boolean,
  belowMinZoom: boolean,
  requestState: MapRequestState,
): string | null => {
  if (!enabled) return null;
  if (belowMinZoom) return "ожидает zoom";
  if (requestState.status === "loading" && requestState.loadableLayerIds.includes(layerId)) {
    return "загрузка";
  }
  if (
    (requestState.status === "ready" || requestState.status === "empty") &&
    requestState.loadedLayerIds.includes(layerId)
  ) {
    return "видим";
  }
  if (requestState.status === "pending-manual-load") return "ожидает";
  return "готов";
};

export function LayerControl({
  visibleLayerIds,
  zoom,
  autoLoad,
  requestState,
  onToggle,
  onAutoLoadChange,
  onLoadObjects,
  onReset,
}: LayerControlProps) {
  const manualLoadPending = requestState.status === "pending-manual-load";
  return (
    <section className="layer-control" aria-labelledby="layers-heading">
      <div className="layer-control__heading">
        <p className="section-label" id="layers-heading">
          Слои
        </p>
        <span>z{zoom.toFixed(1)}</span>
      </div>
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
      <div className="layer-control__list">
        {layerRegistry.map((layer) => {
          const belowMinZoom = zoom < layer.minZoom;
          const enabled = visibleLayerIds.has(layer.id);
          const status = layerStatus(layer.id, enabled, belowMinZoom, requestState);
          return (
            <label className={belowMinZoom ? "layer-toggle layer-toggle--muted" : "layer-toggle"} key={layer.id}>
              <input
                type="checkbox"
                checked={enabled}
                onChange={() => onToggle(layer.id)}
              />
              <span className={`layer-swatch layer-swatch--${layer.id}`} aria-hidden="true" />
              <span>{layer.label}</span>
              <small>{belowMinZoom ? `с z${layer.minZoom}` : status}</small>
            </label>
          );
        })}
      </div>
    </section>
  );
}
