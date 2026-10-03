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

export type MapWorkspaceProps = {
  visibleLayerIds: ReadonlySet<string>;
  autoLoad: boolean;
  manualLoadSequence: number;
  districtIds: readonly string[];
  navigationRequest: MapNavigationRequest | null;
  objectSelection: { id: string; origin: "map" | "search" } | null;
  onObjectSelect: (objectId: string) => void;
  onObjectClose: () => void;
  onZoomChange: (zoom: number) => void;
  onMapRequestStateChange: (state: MapRequestState) => void;
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
  onObjectSelect,
  onObjectClose,
  onZoomChange,
  onMapRequestStateChange,
}: MapWorkspaceProps) {
  const [requestState, setRequestState] = useState<MapRequestState>({ status: "idle" });
  const [cardState, setCardState] = useState<ObjectCardState>({ status: "closed" });
  const detailSequenceRef = useRef(0);
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

  const handleVisibleFeatureIds = useCallback((visibleIds: ReadonlySet<string>) => {
    if (
      objectSelection?.origin === "map" &&
      !visibleIds.has(objectSelection.id)
    ) {
      onObjectClose();
    }
  }, [objectSelection, onObjectClose]);

  const handleMapSelection = useCallback(
    (selection: MapSelection) => {
      if (selection.kind === "canonical-object") onObjectSelect(selection.objectId);
      // A future layer-feature card will subscribe here without entering ObjectDetail.
    },
    [onObjectSelect],
  );

  return (
    <main className="map-workspace" aria-label="Рабочая область карты">
      <MapView
        visibleLayerIds={visibleLayerIds}
        autoLoad={autoLoad}
        manualLoadSequence={manualLoadSequence}
        districtIds={districtIds}
        navigationRequest={navigationRequest}
        selectedFeatureId={selectedObjectId}
        onSelection={handleMapSelection}
        onVisibleFeatureIdsChange={handleVisibleFeatureIds}
        onRequestStateChange={handleRequestStateChange}
        onZoomChange={onZoomChange}
      />
      <RequestStatus state={requestState} />
      <ObjectCard state={cardState} onClose={closeCard} />
    </main>
  );
}
