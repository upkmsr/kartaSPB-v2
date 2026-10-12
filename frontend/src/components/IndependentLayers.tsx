import { useEffect, useMemo, useRef, useState } from "react";
import { fetchScenarioDimensions } from "../api/heatmap";
import { prepareInfluence, type PreparedInfluence } from "../api/influence";
import type { IndependentLayerState } from "../analysis/analysisPreferences";
import { factorRegistry } from "../analysis/factorRegistry";
import { resolveHeatmapGridVersion } from "../map/heatmapResolution";

type IndependentLayersProps = {
  active: boolean;
  zoom: number;
  layers: Record<string, IndependentLayerState>;
  prepared: PreparedInfluence | null;
  accentedFactorId: string | null;
  tileError: string | null;
  onLayersChange: (layers: Record<string, IndependentLayerState>) => void;
  onPrepared: (prepared: PreparedInfluence) => void;
  onHide: () => void;
  onAccentChange: (factorId: string | null) => void;
  onObjectLayerVisibilityChange: (layerId: string, visible: boolean) => void;
};

const defaultLayerState = (): IndependentLayerState => ({
  enabled: false,
  minimumScore: 40,
  showObjects: false,
});

export function IndependentLayers({
  active,
  zoom,
  layers,
  prepared,
  accentedFactorId,
  tileError,
  onLayersChange,
  onPrepared,
  onHide,
  onAccentChange,
  onObjectLayerVisibilityChange,
}: IndependentLayersProps) {
  const [registryReady, setRegistryReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preparing, setPreparing] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const layersRef = useRef(layers);
  const onLayersChangeRef = useRef(onLayersChange);
  const onPreparedRef = useRef(onPrepared);
  const onHideRef = useRef(onHide);
  layersRef.current = layers;
  onLayersChangeRef.current = onLayersChange;
  onPreparedRef.current = onPrepared;
  onHideRef.current = onHide;

  useEffect(() => {
    const controller = new AbortController();
    fetchScenarioDimensions(controller.signal)
      .then((dimensions) => {
        if (controller.signal.aborted) return;
        const published = new Set(dimensions.map((item) => item.metric_key));
        if (factorRegistry.some((factor) => !published.has(factor.metricKey))) {
          setError("Реестр аналитических факторов неполон");
          return;
        }
        const merged = Object.fromEntries(
          factorRegistry.map((factor) => [
            factor.id,
            layersRef.current[factor.id] ?? defaultLayerState(),
          ]),
        );
        onLayersChangeRef.current(merged);
        setRegistryReady(true);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError("Не удалось загрузить факторы");
      });
    return () => controller.abort();
  }, []);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const enabledMetricKeys = useMemo(
    () => factorRegistry
      .filter((factor) => layers[factor.id]?.enabled)
      .map((factor) => factor.metricKey)
      .sort(),
    [layers],
  );
  const gridVersion = resolveHeatmapGridVersion("auto", zoom);
  const requestKey = JSON.stringify([gridVersion, enabledMetricKeys]);
  const preparedKey = prepared === null
    ? null
    : JSON.stringify([prepared.grid_version, prepared.channels.map((channel) => channel.metric_key).sort()]);

  useEffect(() => {
    if (!registryReady || enabledMetricKeys.length === 0) {
      controllerRef.current?.abort();
      if (prepared !== null) onHideRef.current();
      return;
    }
    if (requestKey === preparedKey) return;
    const timer = window.setTimeout(() => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      setPreparing(true);
      setError(null);
      void prepareInfluence(
        { grid_version: gridVersion, metric_keys: enabledMetricKeys },
        controller.signal,
      )
        .then((result) => {
          if (!controller.signal.aborted) onPreparedRef.current(result);
        })
        .catch(() => {
          if (!controller.signal.aborted) setError("Не удалось подготовить слои влияния");
        })
        .finally(() => {
          if (!controller.signal.aborted) setPreparing(false);
        });
    }, 240);
    return () => window.clearTimeout(timer);
  }, [enabledMetricKeys, gridVersion, prepared, preparedKey, registryReady, requestKey]);

  const update = (factorId: string, patch: Partial<IndependentLayerState>): void => {
    const next = {
      ...layers,
      [factorId]: { ...(layers[factorId] ?? defaultLayerState()), ...patch },
    };
    onLayersChange(next);
  };

  return (
    <section className="influence-control" aria-labelledby="influence-heading">
      <div className="influence-control__heading">
        <p className="section-label" id="influence-heading">Слои влияния</p>
        <small>{preparing ? "обновление…" : prepared ? (prepared.grid_version.includes("50m") ? "50 м" : "200 м") : ""}</small>
      </div>
      <p className="influence-control__help">
        Порог меняет только видимую зону, но не физический радиус расчёта и не исходный score.
      </p>
      <div className="influence-control__list">
        {factorRegistry.map((factor) => {
          const state = layers[factor.id] ?? defaultLayerState();
          return (
            <article className="influence-factor" key={factor.id}>
              <div className="influence-factor__title">
                <label>
                  <input
                    type="checkbox"
                    checked={state.enabled}
                    onChange={(event) => update(factor.id, { enabled: event.target.checked })}
                  />
                  <span className="influence-factor__swatch" style={{ background: factor.color }} aria-hidden="true" />
                  <span>{factor.label}</span>
                </label>
                <button
                  type="button"
                  aria-label={`Акцент: ${factor.label}`}
                  aria-pressed={accentedFactorId === factor.id}
                  disabled={!state.enabled}
                  onClick={() => onAccentChange(accentedFactorId === factor.id ? null : factor.id)}
                >
                  Акцент
                </button>
              </div>
              <label className="influence-factor__threshold">
                <span>Минимальный балл влияния</span>
                <input
                  aria-label={`Минимальный балл влияния: ${factor.label}`}
                  type="range"
                  min="0"
                  max="99"
                  value={state.minimumScore}
                  disabled={!state.enabled}
                  onChange={(event) => update(factor.id, { minimumScore: Number(event.target.value) })}
                />
                <output>{state.minimumScore}</output>
              </label>
              <label className="influence-factor__objects">
                <input
                  type="checkbox"
                  checked={state.showObjects}
                  onChange={(event) => {
                    const visible = event.target.checked;
                    update(factor.id, { showObjects: visible });
                    onObjectLayerVisibilityChange(factor.layerId, visible);
                  }}
                />
                <span>Показать исходные объекты</span>
              </label>
            </article>
          );
        })}
      </div>
      {(error || tileError) && <p role="alert" className="heatmap-control__state heatmap-control__state--error">{error ?? tileError}</p>}
      {!factorRegistry.some((factor) => layers[factor.id]?.enabled) && registryReady && (
        <p className="heatmap-control__state">Включите хотя бы один фактор</p>
      )}
      {!active && prepared && <small>Настройки сохранены; на карте сейчас открыт общий анализ.</small>}
    </section>
  );
}
