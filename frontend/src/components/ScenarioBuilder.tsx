import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchScenarioDimensions,
  fetchScoreDistribution,
  prepareHeatmap,
  type PreparedHeatmap,
  type ScenarioDimension,
} from "../api/heatmap";
import {
  DEFAULT_HEATMAP_DISPLAY_RANGE,
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

type ContrastMode = "low" | "medium" | "high" | "ultra" | "manual" | "district";

export type ScenarioBuilderProps = {
  active: boolean;
  activeHeatmap: PreparedHeatmap | null;
  districtIds: readonly string[];
  zoom: number;
  displayRange: HeatmapDisplayRange;
  tileError: string | null;
  inspectEnabled: boolean;
  onPrepared: (heatmap: PreparedHeatmap) => void;
  onDisplayRangeChange: (range: HeatmapDisplayRange) => void;
  onHide: () => void;
  onInspectEnabledChange: (enabled: boolean) => void;
};

const presetRanges: Record<Exclude<ContrastMode, "district" | "manual">, HeatmapDisplayRange> = {
  low: { min: 0, max: 100 },
  medium: { min: 25, max: 100 },
  high: DEFAULT_HEATMAP_DISPLAY_RANGE,
  ultra: { min: 70, max: 100 },
};

const isPresetContrast = (
  mode: ContrastMode,
): mode is Exclude<ContrastMode, "district" | "manual"> =>
  mode !== "district" && mode !== "manual";

const requestKey = (gridVersion: string, weights: Record<string, number>): string =>
  JSON.stringify({ gridVersion, weights: Object.entries(weights).sort(([a], [b]) => a.localeCompare(b)) });

export function ScenarioBuilder({
  active,
  activeHeatmap,
  districtIds,
  zoom,
  displayRange,
  tileError,
  inspectEnabled,
  onPrepared,
  onDisplayRangeChange,
  onHide,
  onInspectEnabledChange,
}: ScenarioBuilderProps) {
  const [loadState, setLoadState] = useState<LoadState>({ status: "loading" });
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [resolutionMode, setResolutionMode] = useState<HeatmapResolutionMode>("auto");
  const [contrastMode, setContrastMode] = useState<ContrastMode>("high");
  const [manualRange, setManualRange] = useState<HeatmapDisplayRange>(
    DEFAULT_HEATMAP_DISPLAY_RANGE,
  );
  const [activated, setActivated] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const prepareController = useRef<AbortController | null>(null);
  const distributionController = useRef<AbortController | null>(null);
  const lastPreparedKey = useRef<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchScenarioDimensions(controller.signal)
      .then((dimensions) => {
        if (controller.signal.aborted) return;
        setLoadState({ status: "loaded", dimensions });
        setWeights(Object.fromEntries(dimensions.map((item) => [item.metric_key, 0])));
      })
      .catch(() => {
        if (!controller.signal.aborted) setLoadState({ status: "error" });
      });
    return () => controller.abort();
  }, []);

  useEffect(
    () => () => {
      prepareController.current?.abort();
      distributionController.current?.abort();
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
          if (isPresetContrast(contrastMode)) {
            onDisplayRangeChange({ ...presetRanges[contrastMode] });
          } else if (contrastMode === "manual") {
            onDisplayRangeChange({ ...manualRange });
          }
          onPrepared(prepared);
        })
        .catch(() => {
          if (!controller.signal.aborted) setError("Не удалось рассчитать сценарий");
        })
        .finally(() => {
          if (!controller.signal.aborted) setPreparing(false);
        });
    }, [
      contrastMode,
      hasWeights,
      manualDetailBlocked,
      manualRange,
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
    if (contrastMode !== "district") return;
    if (districtIds.length === 0) {
      setContrastMode("high");
      onDisplayRangeChange({ ...DEFAULT_HEATMAP_DISPLAY_RANGE });
      return;
    }
    if (!active || !activeHeatmap || !hasWeights) return;
    distributionController.current?.abort();
    const controller = new AbortController();
    distributionController.current = controller;
    void fetchScoreDistribution(
      {
        grid_version: activeHeatmap.grid_version,
        weights: selectedWeights,
        district_ids: [...districtIds].sort(),
      },
      controller.signal,
    )
      .then((distribution) => {
        if (
          controller.signal.aborted ||
          distribution.scoring_signature !== activeHeatmap.scoring_signature
        ) return;
        if (distribution.p90 > distribution.p10) {
          onDisplayRangeChange({ min: distribution.p10, max: distribution.p90 });
        } else {
          setError("В выбранном районе недостаточно различий для относительной шкалы");
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setError("Не удалось сравнить выбранные районы");
      });
    return () => controller.abort();
  }, [active, activeHeatmap, contrastMode, districtIds, hasWeights, onDisplayRangeChange, selectedWeights]);

  useEffect(() => {
    if (hasWeights) return;
    prepareController.current?.abort();
    distributionController.current?.abort();
    lastPreparedKey.current = null;
    setActivated(false);
    setPreparing(false);
    setError(null);
    if (active || activeHeatmap) onHide();
  }, [active, activeHeatmap, hasWeights, onHide]);

  const updateWeight = (metricKey: string, value: number): void => {
    setWeights((current) => ({ ...current, [metricKey]: value }));
  };

  const setAll = (value: number): void => {
    setWeights(Object.fromEntries(dimensions.map((item) => [item.metric_key, value])));
    if (value === 0) {
      prepareController.current?.abort();
      distributionController.current?.abort();
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
    distributionController.current?.abort();
    onHide();
  };

  const selectContrast = (mode: ContrastMode): void => {
    if (mode === "district" && districtIds.length === 0) return;
    setContrastMode(mode);
    setError(null);
    if (isPresetContrast(mode)) onDisplayRangeChange({ ...presetRanges[mode] });
    if (mode === "manual") onDisplayRangeChange({ ...manualRange });
  };

  const updateManualRange = (edge: "min" | "max", value: number): void => {
    const next = edge === "min"
      ? { min: Math.min(Math.max(value, 0), manualRange.max - 1), max: manualRange.max }
      : { min: manualRange.min, max: Math.max(Math.min(value, 100), manualRange.min + 1) };
    setManualRange(next);
    setContrastMode("manual");
    setError(null);
    onDisplayRangeChange(next);
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
          <fieldset className="heatmap-control__choice-group">
            <legend>Контраст карты</legend>
            <div className="heatmap-control__segments">
              {(["low", "medium", "high", "ultra", "manual", "district"] as const).map((mode) => (
                <button
                  aria-pressed={contrastMode === mode}
                  disabled={mode === "district" && districtIds.length === 0}
                  key={mode}
                  type="button"
                  onClick={() => selectContrast(mode)}
                >
                  {{ low: "Низкий", medium: "Средний", high: "Высокий", ultra: "Очень высокий", manual: "Вручную", district: "По району" }[mode]}
                </button>
              ))}
            </div>
            {contrastMode === "district" && <small>Сравнение внутри выбранного района</small>}
            {contrastMode === "manual" && (
              <div className="scenario-builder__manual-range">
                <label>
                  <span>Минимальный отображаемый балл</span>
                  <input
                    type="range"
                    aria-label="Минимальный отображаемый балл"
                    min="0"
                    max="99"
                    value={manualRange.min}
                    onChange={(event) => updateManualRange("min", Number(event.target.value))}
                  />
                  <output>{manualRange.min}</output>
                </label>
                <label>
                  <span>Максимальный отображаемый балл</span>
                  <input
                    type="range"
                    aria-label="Максимальный отображаемый балл"
                    min="1"
                    max="100"
                    value={manualRange.max}
                    onChange={(event) => updateManualRange("max", Number(event.target.value))}
                  />
                  <output>{manualRange.max}</output>
                </label>
                <small>Значения ниже минимума и выше максимума визуально обрезаются; аналитический балл не меняется.</small>
              </div>
            )}
          </fieldset>
          <fieldset className="heatmap-control__choice-group">
            <legend>Детализация</legend>
            <div className="heatmap-control__segments">
              {([ ["auto", "Авто"], ["200m", "200 м"], ["50m", "50 м"] ] as const).map(([mode, label]) => (
                <button
                  aria-pressed={resolutionMode === mode}
                  disabled={mode === "50m" && zoom < AUTO_DETAIL_MIN_ZOOM}
                  key={mode}
                  type="button"
                  onClick={() => setResolutionMode(mode)}
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
          <span>{contrastMode === "district" ? "Сравнение внутри выбранного района" : `Цветовой диапазон: ${displayRange.min.toFixed(0)}–${displayRange.max.toFixed(0)}. Аналитический балл: 0–100.`}</span>
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
