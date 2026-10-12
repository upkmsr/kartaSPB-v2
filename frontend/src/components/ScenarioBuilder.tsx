import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchScenarioDimensions,
  prepareHeatmap,
  type PreparedHeatmap,
  type ScenarioDimension,
} from "../api/heatmap";
import {
  HEATMAP_COLORS,
  heatmapLegendValues,
  type HeatmapDisplayRange,
} from "../map/heatmapOverlay";
import {
  AUTO_DETAIL_MIN_ZOOM,
  DETAIL_GRID_VERSION,
  resolveHeatmapGridVersion,
  type HeatmapResolutionMode,
} from "../map/heatmapResolution";

type LoadState =
  | { status: "loading" }
  | { status: "loaded"; dimensions: ScenarioDimension[] }
  | { status: "error" };

export type ScenarioBuilderProps = {
  active: boolean;
  activeHeatmap: PreparedHeatmap | null;
  districtIds?: readonly string[];
  zoom: number;
  displayRange: HeatmapDisplayRange;
  tileError: string | null;
  inspectEnabled: boolean;
  weights?: Record<string, number>;
  minimumScore?: number;
  onWeightsChange?: (weights: Record<string, number>) => void;
  onMinimumScoreChange?: (minimumScore: number) => void;
  resolutionMode?: HeatmapResolutionMode;
  onResolutionModeChange?: (mode: HeatmapResolutionMode) => void;
  onPrepared: (heatmap: PreparedHeatmap) => void;
  onDisplayRangeChange: (range: HeatmapDisplayRange) => void;
  onHide: () => void;
  onInspectEnabledChange: (enabled: boolean) => void;
};

const requestKey = (gridVersion: string, weights: Record<string, number>): string =>
  JSON.stringify({ gridVersion, weights: Object.entries(weights).sort(([a], [b]) => a.localeCompare(b)) });

export function ScenarioBuilder({
  active,
  activeHeatmap,
  zoom,
  displayRange,
  tileError,
  inspectEnabled,
  weights: controlledWeights,
  minimumScore: controlledMinimumScore,
  onWeightsChange = () => undefined,
  onMinimumScoreChange = () => undefined,
  resolutionMode: controlledResolutionMode,
  onResolutionModeChange = () => undefined,
  onPrepared,
  onDisplayRangeChange,
  onHide,
  onInspectEnabledChange,
}: ScenarioBuilderProps) {
  const [loadState, setLoadState] = useState<LoadState>({ status: "loading" });
  const [localWeights, setLocalWeights] = useState<Record<string, number>>({});
  const [localMinimumScore, setLocalMinimumScore] = useState(40);
  const [localResolutionMode, setLocalResolutionMode] = useState<HeatmapResolutionMode>("auto");
  const [activated, setActivated] = useState(active);
  const [preparing, setPreparing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const prepareController = useRef<AbortController | null>(null);
  const lastPreparedKey = useRef<string | null>(null);
  const initialWeightsRef = useRef(controlledWeights ?? {});
  const weightsControlledRef = useRef(controlledWeights !== undefined);
  const weightsChangeRef = useRef(onWeightsChange);
  weightsChangeRef.current = onWeightsChange;
  const weights = controlledWeights ?? localWeights;
  const minimumScore = controlledMinimumScore ?? localMinimumScore;
  const resolutionMode = controlledResolutionMode ?? localResolutionMode;

  const commitWeights = (next: Record<string, number>): void => {
    if (controlledWeights === undefined) setLocalWeights(next);
    onWeightsChange(next);
  };

  useEffect(() => {
    const controller = new AbortController();
    fetchScenarioDimensions(controller.signal)
      .then((dimensions) => {
        if (controller.signal.aborted) return;
        setLoadState({ status: "loaded", dimensions });
        const initialWeights = Object.fromEntries(
          dimensions.map((item) => [
            item.metric_key,
            initialWeightsRef.current[item.metric_key] ?? 0,
          ]),
        );
        if (!weightsControlledRef.current) setLocalWeights(initialWeights);
        weightsChangeRef.current(initialWeights);
      })
      .catch(() => {
        if (!controller.signal.aborted) setLoadState({ status: "error" });
      });
    return () => controller.abort();
  }, []); // Initial registry merge only; user changes remain controlled by App.

  useEffect(
    () => () => {
      prepareController.current?.abort();
    },
    [],
  );

  const dimensions = useMemo(
    () => (loadState.status === "loaded" ? loadState.dimensions : []),
    [loadState],
  );
  const selectedWeights = useMemo(
    () =>
      Object.fromEntries(
        dimensions
          .map((dimension) => [dimension.metric_key, weights[dimension.metric_key] ?? 0] as const)
          .filter(([, weight]) => weight > 0)
          .sort(([left], [right]) => left.localeCompare(right)),
      ),
    [dimensions, weights],
  );
  const hasWeights = Object.keys(selectedWeights).length > 0;
  const resolvedGrid = resolveHeatmapGridVersion(resolutionMode, zoom);
  const manualDetailBlocked = resolutionMode === "50m" && zoom < AUTO_DETAIL_MIN_ZOOM;
  const canonicalRequestKey = requestKey(resolvedGrid, selectedWeights);

  const prepare = useCallback(
    (key: string) => {
      if (!hasWeights || manualDetailBlocked || lastPreparedKey.current === key) return;
      prepareController.current?.abort();
      const controller = new AbortController();
      prepareController.current = controller;
      setPreparing(true);
      setError(null);
      void prepareHeatmap(
        { grid_version: resolvedGrid, weights: selectedWeights },
        controller.signal,
      )
        .then((prepared) => {
          if (controller.signal.aborted) return;
          lastPreparedKey.current = key;
          onDisplayRangeChange({ min: minimumScore, max: 100 });
          onPrepared(prepared);
        })
        .catch(() => {
          if (!controller.signal.aborted) setError("Не удалось рассчитать сценарий");
        })
        .finally(() => {
          if (!controller.signal.aborted) setPreparing(false);
        });
    }, [
      hasWeights,
      manualDetailBlocked,
      minimumScore,
      onDisplayRangeChange,
      onPrepared,
      resolvedGrid,
      selectedWeights,
    ]);

  useEffect(() => {
    if (!activated || !active || !hasWeights || manualDetailBlocked) return;
    const timer = window.setTimeout(() => prepare(canonicalRequestKey), 320);
    return () => window.clearTimeout(timer);
  }, [active, activated, canonicalRequestKey, hasWeights, manualDetailBlocked, prepare]);

  useEffect(() => {
    if (hasWeights) return;
    prepareController.current?.abort();
    lastPreparedKey.current = null;
    setActivated(false);
    setPreparing(false);
    setError(null);
    if (active || activeHeatmap) onHide();
  }, [active, activeHeatmap, hasWeights, onHide]);

  const updateWeight = (metricKey: string, value: number): void => {
    commitWeights({ ...weights, [metricKey]: value });
  };

  const setAll = (value: number): void => {
    commitWeights(Object.fromEntries(dimensions.map((item) => [item.metric_key, value])));
    if (value === 0) {
      prepareController.current?.abort();
      setActivated(false);
      setPreparing(false);
      lastPreparedKey.current = null;
      onHide();
    }
  };

  const activate = (): void => {
    if (!hasWeights || manualDetailBlocked) return;
    setActivated(true);
    prepare(canonicalRequestKey);
  };

  const hide = (): void => {
    setActivated(false);
    lastPreparedKey.current = null;
    prepareController.current?.abort();
    onHide();
  };

  const updateMinimumScore = (value: number): void => {
    const next = Math.min(99, Math.max(0, value));
    if (controlledMinimumScore === undefined) setLocalMinimumScore(next);
    onMinimumScoreChange(next);
    onDisplayRangeChange({ min: next, max: 100 });
  };

  const updateResolutionMode = (mode: HeatmapResolutionMode): void => {
    if (controlledResolutionMode === undefined) setLocalResolutionMode(mode);
    onResolutionModeChange(mode);
  };

  const groups = dimensions.reduce<Array<{ key: string; label: string; items: ScenarioDimension[] }>>(
    (result, dimension) => {
      const existing = result.find((item) => item.key === dimension.group);
      if (existing) existing.items.push(dimension);
      else result.push({ key: dimension.group, label: dimension.group_label, items: [dimension] });
      return result;
    },
    [],
  );

  return (
    <section className="scenario-builder" aria-labelledby="scenario-heading">
      <p className="section-label" id="scenario-heading">Приоритеты</p>
      {loadState.status === "loading" && <p role="status">Загружаем факторы…</p>}
      {loadState.status === "error" && <p role="alert">Не удалось загрузить факторы</p>}
      {loadState.status === "loaded" && (
        <>
          {groups.map((group) => (
            <fieldset className="scenario-builder__group" key={group.key}>
              <legend>{group.label}</legend>
              {group.items.map((dimension) => (
                <label className="scenario-builder__slider" key={dimension.key}>
                  <span>{dimension.label}</span>
                  <input
                    aria-label={dimension.label}
                    type="range"
                    min="0"
                    max="100"
                    step="1"
                    value={weights[dimension.metric_key] ?? 0}
                    onChange={(event) => updateWeight(dimension.metric_key, Number(event.target.value))}
                  />
                  <output>{weights[dimension.metric_key] ?? 0}</output>
                </label>
              ))}
            </fieldset>
          ))}
          <div className="scenario-builder__quick-actions">
            <button type="button" onClick={() => setAll(50)}>Все поровну</button>
            <button type="button" onClick={() => setAll(0)}>Сбросить</button>
          </div>
          <label className="scenario-builder__minimum">
            <span>Минимальный отображаемый балл</span>
            <input
              type="range"
              aria-label="Минимальный отображаемый балл"
              min="0"
              max="99"
              value={minimumScore}
              onChange={(event) => updateMinimumScore(Number(event.target.value))}
            />
            <output>{minimumScore}</output>
            <small>Ниже порога ячейки прозрачны. Исходный балл и расчёт не изменяются.</small>
          </label>
          <fieldset className="heatmap-control__choice-group">
            <legend>Детализация</legend>
            <div className="heatmap-control__segments">
              {([ ["auto", "Авто"], ["200m", "200 м"], ["50m", "50 м"] ] as const).map(([mode, label]) => (
                <button
                  aria-pressed={resolutionMode === mode}
                  disabled={mode === "50m" && zoom < AUTO_DETAIL_MIN_ZOOM}
                  key={mode}
                  type="button"
                  onClick={() => updateResolutionMode(mode)}
                >{label}</button>
              ))}
            </div>
            <small>
              {resolutionMode === "auto"
                ? `Авто: ${zoom >= AUTO_DETAIL_MIN_ZOOM ? "50 м" : "200 м"} при z${Math.floor(zoom)}`
                : manualDetailBlocked ? "50 м доступно с z13" : `Выбрано: ${resolutionMode === "50m" ? "50 м" : "200 м"}`}
            </small>
          </fieldset>
          <div className="heatmap-control__actions">
            <button type="button" disabled={!hasWeights || preparing || manualDetailBlocked} onClick={activate}>
              {preparing ? "Расчёт…" : "Показать сценарий"}
            </button>
            {active && <button type="button" className="heatmap-control__hide" onClick={hide}>Скрыть</button>}
          </div>
          {active && activeHeatmap && (
            <button
              type="button"
              className="scenario-builder__inspect"
              aria-pressed={inspectEnabled}
              onClick={() => onInspectEnabledChange(!inspectEnabled)}
            >
              Почему здесь такой балл?
            </button>
          )}
        </>
      )}
      {(error || tileError) && <p className="heatmap-control__state heatmap-control__state--error" role="alert">{error ?? tileError}</p>}
      {!hasWeights && loadState.status === "loaded" && (
        <p className="heatmap-control__state">Выберите хотя бы один приоритет</p>
      )}
      {active && activeHeatmap && (
        <div className="heatmap-legend" aria-label="Легенда персонального сценария">
          <strong>Персональный сценарий</strong>
          <span>{`Цветовой диапазон: ${displayRange.min.toFixed(0)}–100. Аналитический балл: 0–100.`}</span>
          <div className="heatmap-legend__scale" aria-hidden="true" />
          <div className="heatmap-legend__values">
            {heatmapLegendValues(displayRange).map((value, index) => <span key={`${value}-${index}`} style={{ color: HEATMAP_COLORS[index] }}>{value.toFixed(0)}</span>)}
          </div>
          <small>Сетка: {activeHeatmap.grid_version === DETAIL_GRID_VERSION ? "50 м" : "200 м"}</small>
          <ul className="scenario-builder__active-weights">
            {dimensions.filter((item) => (activeHeatmap.weights[item.metric_key] ?? 0) > 0).map((item) => (
              <li key={item.key}><span>{item.label}</span><strong>{activeHeatmap.weights[item.metric_key]}</strong></li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
