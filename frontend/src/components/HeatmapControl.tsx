import { useEffect, useRef, useState } from "react";
import {
  fetchNormalizationProfiles,
  prepareHeatmap,
  type NormalizationProfile,
  type PreparedHeatmap,
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

type ProfilesState =
  | { status: "loading" }
  | { status: "loaded"; profiles: NormalizationProfile[] }
  | { status: "error" };

export type HeatmapControlProps = {
  activeHeatmap: PreparedHeatmap | null;
  tileError: string | null;
  onPrepared: (heatmap: PreparedHeatmap) => void;
  onHide: () => void;
  displayRange?: HeatmapDisplayRange;
  onDisplayRangeChange?: (range: HeatmapDisplayRange) => void;
  zoom?: number;
};

const contrastPresets = [
  { key: "low", label: "Низкий", range: { min: 0, max: 100 } },
  { key: "medium", label: "Средний", range: { min: 25, max: 100 } },
  { key: "high", label: "Высокий", range: DEFAULT_HEATMAP_DISPLAY_RANGE },
] as const;

export function HeatmapControl({
  activeHeatmap,
  tileError,
  onPrepared,
  onHide,
  displayRange = DEFAULT_HEATMAP_DISPLAY_RANGE,
  onDisplayRangeChange = () => undefined,
  zoom = 12,
}: HeatmapControlProps) {
  const [profilesState, setProfilesState] = useState<ProfilesState>({ status: "loading" });
  const [selectedMetric, setSelectedMetric] = useState("");
  const [preparing, setPreparing] = useState(false);
  const [prepareError, setPrepareError] = useState<string | null>(null);
  const [resolutionMode, setResolutionMode] = useState<HeatmapResolutionMode>("auto");
  const prepareControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchNormalizationProfiles(controller.signal)
      .then((profiles) => {
        if (!controller.signal.aborted) setProfilesState({ status: "loaded", profiles });
      })
      .catch(() => {
        if (!controller.signal.aborted) setProfilesState({ status: "error" });
      });
    return () => controller.abort();
  }, []);

  useEffect(
    () => () => {
      prepareControllerRef.current?.abort();
    },
    [],
  );

  const selectedProfile =
    profilesState.status === "loaded"
      ? profilesState.profiles.find((profile) => profile.metric_key === selectedMetric) ?? null
      : null;
  const activeProfile =
    profilesState.status === "loaded" && activeHeatmap
      ? profilesState.profiles.find(
          (profile) => profile.metric_key === Object.keys(activeHeatmap.weights)[0],
        ) ?? null
      : null;

  const activate = (): void => {
    if (!selectedMetric || preparing) return;
    prepareControllerRef.current?.abort();
    const controller = new AbortController();
    prepareControllerRef.current = controller;
    setPreparing(true);
    setPrepareError(null);
    void prepareHeatmap(
      {
        grid_version: resolveHeatmapGridVersion(resolutionMode, zoom),
        weights: { [selectedMetric]: 100 },
      },
      controller.signal,
    )
      .then((prepared) => {
        if (!controller.signal.aborted) onPrepared(prepared);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setPrepareError("Не удалось подготовить тепловую карту");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setPreparing(false);
      });
  };

  return (
    <section className="heatmap-control" aria-labelledby="heatmap-heading">
      <p className="section-label" id="heatmap-heading">
        Тепловая карта
      </p>
      {profilesState.status === "loading" && (
        <p className="heatmap-control__state" role="status">
          Загружаем показатели…
        </p>
      )}
      {profilesState.status === "error" && (
        <p className="heatmap-control__state heatmap-control__state--error" role="alert">
          Не удалось загрузить показатели
        </p>
      )}
      {profilesState.status === "loaded" && (
        <>
          <label className="heatmap-control__selector">
            <span>Показатель</span>
            <select
              aria-label="Показатель тепловой карты"
              value={selectedMetric}
              onChange={(event) => setSelectedMetric(event.target.value)}
            >
              <option value="">Не выбран</option>
              {profilesState.profiles.map((profile) => (
                <option value={profile.metric_key} key={profile.metric_key}>
                  {profile.label}
                </option>
              ))}
            </select>
          </label>
          <fieldset className="heatmap-control__choice-group">
            <legend>Контраст карты</legend>
            <div className="heatmap-control__segments">
              {contrastPresets.map((preset) => {
                const selected =
                  displayRange.min === preset.range.min &&
                  displayRange.max === preset.range.max;
                return (
                  <button
                    aria-pressed={selected}
                    key={preset.key}
                    type="button"
                    onClick={() => onDisplayRangeChange({ ...preset.range })}
                  >
                    {preset.label}
                  </button>
                );
              })}
            </div>
          </fieldset>
          <fieldset className="heatmap-control__choice-group">
            <legend>Детализация</legend>
            <div className="heatmap-control__segments">
              {([
                ["auto", "Авто"],
                ["200m", "200 м"],
                ["50m", "50 м"],
              ] as const).map(([mode, label]) => (
                <button
                  aria-pressed={resolutionMode === mode}
                  key={mode}
                  type="button"
                  onClick={() => setResolutionMode(mode)}
                >
                  {label}
                </button>
              ))}
            </div>
            <small>
              {resolutionMode === "auto"
                ? `Авто: ${zoom >= AUTO_DETAIL_MIN_ZOOM ? "50 м" : "200 м"} при z${Math.floor(zoom)}`
                : `Выбрано: ${resolutionMode === "50m" ? "50 м" : "200 м"}`}
            </small>
          </fieldset>
          <div className="heatmap-control__actions">
            <button type="button" disabled={!selectedProfile || preparing} onClick={activate}>
              {preparing ? "Подготовка…" : "Показать"}
            </button>
            {activeHeatmap && (
              <button type="button" className="heatmap-control__hide" onClick={onHide}>
                Скрыть
              </button>
            )}
          </div>
        </>
      )}
      {(prepareError || tileError) && (
        <p className="heatmap-control__state heatmap-control__state--error" role="alert">
          {prepareError ?? tileError}
        </p>
      )}
      {activeHeatmap && (
        <div className="heatmap-legend" aria-label="Легенда тепловой карты">
          <strong>{activeProfile?.label ?? Object.keys(activeHeatmap.weights)[0]}</strong>
          <span>
            Цветовой диапазон: {displayRange.min}–{displayRange.max}. Аналитический балл:
            0–100.
          </span>
          <div className="heatmap-legend__scale" aria-hidden="true" />
          <div className="heatmap-legend__values">
            {heatmapLegendValues(displayRange).map((value, index) => (
              <span key={value} style={{ color: HEATMAP_COLORS[index] }}>
                {Number.isInteger(value) ? value : value.toFixed(1)}
              </span>
            ))}
          </div>
          {displayRange.min > 0 && (
            <small>Баллы ниже {displayRange.min} отображаются минимальным цветом.</small>
          )}
          <small>
            Сетка: {activeHeatmap.grid_version === DETAIL_GRID_VERSION ? "50 м" : "200 м"}
          </small>
          <div className="heatmap-legend__direction">
            <span>хуже</span>
            <span>лучше</span>
          </div>
        </div>
      )}
    </section>
  );
}
