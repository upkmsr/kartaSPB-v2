import { useEffect, useRef, useState } from "react";
import {
  fetchNormalizationProfiles,
  prepareHeatmap,
  type NormalizationProfile,
  type PreparedHeatmap,
} from "../api/heatmap";

type ProfilesState =
  | { status: "loading" }
  | { status: "loaded"; profiles: NormalizationProfile[] }
  | { status: "error" };

export type HeatmapControlProps = {
  activeHeatmap: PreparedHeatmap | null;
  tileError: string | null;
  onPrepared: (heatmap: PreparedHeatmap) => void;
  onHide: () => void;
};

const legendStops = [
  { value: 0, color: "#d73027" },
  { value: 25, color: "#fc8d59" },
  { value: 50, color: "#fee08b" },
  { value: 75, color: "#91cf60" },
  { value: 100, color: "#1a9850" },
] as const;

export function HeatmapControl({
  activeHeatmap,
  tileError,
  onPrepared,
  onHide,
}: HeatmapControlProps) {
  const [profilesState, setProfilesState] = useState<ProfilesState>({ status: "loading" });
  const [selectedMetric, setSelectedMetric] = useState("");
  const [preparing, setPreparing] = useState(false);
  const [prepareError, setPrepareError] = useState<string | null>(null);
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
    void prepareHeatmap({ weights: { [selectedMetric]: 100 } }, controller.signal)
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
          <span>Нормализованная полезность, 0–100</span>
          <div className="heatmap-legend__scale" aria-hidden="true" />
          <div className="heatmap-legend__values">
            {legendStops.map((stop) => (
              <span key={stop.value} style={{ color: stop.color }}>
                {stop.value}
              </span>
            ))}
          </div>
          <div className="heatmap-legend__direction">
            <span>хуже</span>
            <span>лучше</span>
          </div>
        </div>
      )}
    </section>
  );
}
