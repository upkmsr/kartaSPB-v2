import { useCallback, useEffect, useRef, useState } from "react";
import { MapView } from "../map/MapView";
import { fetchObjectDetail, MapApiError } from "../map/mapApi";
import type {
  MapNavigationRequest,
  MapRequestState,
  ObjectCardState,
} from "../map/mapTypes";
import { ObjectCard } from "./ObjectCard";
import type { MapSelection } from "../map/layerContract";
import {
  fetchScenarioExplanation,
  type PreparedHeatmap,
} from "../api/heatmap";
import {
  DEFAULT_HEATMAP_DISPLAY_RANGE,
  type HeatmapDisplayRange,
} from "../map/heatmapOverlay";
import {
  ScenarioExplanationCard,
  type ScenarioExplanationState,
} from "./ScenarioExplanationCard";
import type { AnalysisMode, IndependentLayerState } from "../analysis/analysisPreferences";
import type { PreparedInfluence } from "../api/influence";
import { factorByMetric } from "../analysis/factorRegistry";
import {
  InfluenceInspectorCard,
  type InfluenceInspection,
} from "./InfluenceInspectorCard";

export type MapWorkspaceProps = {
  visibleLayerIds: ReadonlySet<string>;
  autoLoad: boolean;
  manualLoadSequence: number;
  districtIds: readonly string[];
  navigationRequest: MapNavigationRequest | null;
  objectSelection: { id: string; origin: "map" | "search" } | null;
  activeHeatmap?: PreparedHeatmap | null;
  activeAnalysisMode?: AnalysisMode;
  preparedInfluence?: PreparedInfluence | null;
  influenceLayers?: Record<string, IndependentLayerState>;
  accentedFactorId?: string | null;
  heatmapDisplayRange?: HeatmapDisplayRange;
  heatmapInspectionEnabled?: boolean;
  onObjectSelect: (objectId: string) => void;
  onObjectClose: () => void;
  onZoomChange: (zoom: number) => void;
  onMapRequestStateChange: (state: MapRequestState) => void;
  onHeatmapError?: () => void;
};

const RequestStatus = ({ state }: { state: MapRequestState }) => {
  if (state.status === "idle") return null;

  const copy = {
    loading: "Загружаем объекты…",
    ready: `${state.status === "ready" ? state.featureCount : 0} объектов`,
    empty: "В этом окне объектов нет",
    "pending-manual-load": "Карта изменена — загрузите объекты",
    "no-enabled-layers": "Включите хотя бы один слой",
    "waiting-for-zoom": "Приблизьте карту до масштаба включённых слоёв",
    "bbox-too-large": "Приблизьте карту для загрузки объектов",
    "feature-limit": "Слишком много объектов — приблизьте карту или отключите слои",
    "stale-error": state.status === "stale-error" ? state.message : "Показаны ранее загруженные данные",
    error: state.status === "error" ? state.message : "Ошибка загрузки",
  }[state.status];

  return (
    <div className={`map-request-state map-request-state--${state.status}`} role="status">
      {state.status === "loading" && <span className="loading-dot" />}
      <span>{copy}</span>
      {(state.status === "ready" || state.status === "empty") && (
        <small>{Math.round(state.durationMs)} ms</small>
      )}
    </div>
  );
};

export function MapWorkspace({
  visibleLayerIds,
  autoLoad,
  manualLoadSequence,
  districtIds,
  navigationRequest,
  objectSelection,
  activeHeatmap = null,
  activeAnalysisMode = "composite",
  preparedInfluence = null,
  influenceLayers = {},
  accentedFactorId = null,
  heatmapDisplayRange = DEFAULT_HEATMAP_DISPLAY_RANGE,
  heatmapInspectionEnabled = false,
  onObjectSelect,
  onObjectClose,
  onZoomChange,
  onMapRequestStateChange,
  onHeatmapError = () => undefined,
}: MapWorkspaceProps) {
  const [requestState, setRequestState] = useState<MapRequestState>({ status: "idle" });
  const [cardState, setCardState] = useState<ObjectCardState>({ status: "closed" });
  const detailSequenceRef = useRef(0);
  const explanationSequenceRef = useRef(0);
  const explanationControllerRef = useRef<AbortController | null>(null);
  const [explanationState, setExplanationState] = useState<ScenarioExplanationState>({
    status: "closed",
  });
  const [influenceInspection, setInfluenceInspection] = useState<InfluenceInspection | null>(null);
  const selectedObjectId = objectSelection?.id ?? null;

  useEffect(() => {
    if (selectedObjectId === null) {
      setCardState({ status: "closed" });
      return;
    }

    const objectId = selectedObjectId;
    const controller = new AbortController();
    const sequence = ++detailSequenceRef.current;
    setCardState({ status: "loading", objectId });
    void fetchObjectDetail(objectId, controller.signal)
      .then((detail) => {
        if (sequence === detailSequenceRef.current && !controller.signal.aborted) {
          setCardState({ status: "loaded", detail });
        }
      })
      .catch((error: unknown) => {
        if (sequence !== detailSequenceRef.current || controller.signal.aborted) return;
        setCardState(
          error instanceof MapApiError && error.status === 404
            ? { status: "not-found", objectId }
            : { status: "error", objectId },
        );
      });

    return () => controller.abort();
  }, [selectedObjectId]);

  const closeCard = useCallback(() => {
    detailSequenceRef.current += 1;
    onObjectClose();
  }, [onObjectClose]);

  const handleRequestStateChange = useCallback(
    (state: MapRequestState) => {
      setRequestState(state);
      onMapRequestStateChange(state);
    },
    [onMapRequestStateChange],
  );

  const handleVisibleFeatureIds = useCallback(() => {
    // Selection is application state, not viewport state. A catalog reload may
    // temporarily omit a selected feature and must not close its ObjectCard.
  }, []);

  const handleMapSelection = useCallback(
    (selection: MapSelection) => {
      if (selection.kind === "canonical-object") onObjectSelect(selection.objectId);
      // A future layer-feature card will subscribe here without entering ObjectDetail.
    },
    [onObjectSelect],
  );

  useEffect(() => {
    explanationControllerRef.current?.abort();
    explanationSequenceRef.current += 1;
    setExplanationState({ status: "closed" });
  }, [activeHeatmap?.scoring_signature, heatmapInspectionEnabled]);

  useEffect(() => {
    setInfluenceInspection(null);
  }, [activeAnalysisMode, preparedInfluence?.influence_signature, influenceLayers]);

  const explainCell = useCallback((cellId: string) => {
    if (!heatmapInspectionEnabled || !activeHeatmap) return;
    explanationControllerRef.current?.abort();
    const controller = new AbortController();
    explanationControllerRef.current = controller;
    const sequence = ++explanationSequenceRef.current;
    const signature = activeHeatmap.scoring_signature;
    setExplanationState({ status: "loading", cellId });
    void fetchScenarioExplanation(
      { cell_id: cellId, spec: activeHeatmap.spec },
      controller.signal,
    )
      .then((explanation) => {
        if (
          !controller.signal.aborted &&
          sequence === explanationSequenceRef.current &&
          explanation.scoring_signature === signature
        ) {
          setExplanationState({ status: "loaded", explanation });
        }
      })
      .catch(() => {
        if (!controller.signal.aborted && sequence === explanationSequenceRef.current) {
          setExplanationState({ status: "error", cellId });
        }
      });
  }, [activeHeatmap, heatmapInspectionEnabled]);

  const closeExplanation = useCallback(() => {
    explanationControllerRef.current?.abort();
    explanationSequenceRef.current += 1;
    setExplanationState({ status: "closed" });
  }, []);

  const inspectInfluenceCell = useCallback((properties: Record<string, unknown>) => {
    if (activeAnalysisMode !== "independent" || preparedInfluence === null) return;
    const cellId = properties.cell_id;
    if (typeof cellId !== "string") return;
    const scores = preparedInfluence.channels.flatMap((channel) => {
      const factor = factorByMetric.get(channel.metric_key);
      const score = properties[channel.property_name];
      const state = factor ? influenceLayers[factor.id] : undefined;
      return factor && state?.enabled && typeof score === "number"
        ? [{
            metricKey: channel.metric_key,
            score,
            minimumScore: state.minimumScore,
            scoreRunId: channel.score_run_id,
          }]
        : [];
    });
    setInfluenceInspection({ cellId, scores });
  }, [activeAnalysisMode, influenceLayers, preparedInfluence]);

  return (
    <main className="map-workspace" aria-label="Рабочая область карты">
      <MapView
        visibleLayerIds={visibleLayerIds}
        autoLoad={autoLoad}
        manualLoadSequence={manualLoadSequence}
        districtIds={districtIds}
        navigationRequest={navigationRequest}
        selectedFeatureId={selectedObjectId}
        activeHeatmap={activeAnalysisMode === "composite" ? activeHeatmap : null}
        activeInfluence={activeAnalysisMode === "independent" && preparedInfluence ? {
          prepared: preparedInfluence,
          layers: influenceLayers,
          accentedFactorId,
        } : null}
        heatmapDisplayRange={heatmapDisplayRange}
        heatmapInspectionEnabled={heatmapInspectionEnabled}
        onSelection={handleMapSelection}
        onVisibleFeatureIdsChange={handleVisibleFeatureIds}
        onRequestStateChange={handleRequestStateChange}
        onZoomChange={onZoomChange}
        onHeatmapError={onHeatmapError}
        onHeatmapCellSelect={explainCell}
        onInfluenceCellSelect={inspectInfluenceCell}
      />
      <RequestStatus state={requestState} />
      <ObjectCard state={cardState} onClose={closeCard} />
      <ScenarioExplanationCard state={explanationState} onClose={closeExplanation} />
      <InfluenceInspectorCard
        inspection={influenceInspection}
        onClose={() => setInfluenceInspection(null)}
      />
    </main>
  );
}
