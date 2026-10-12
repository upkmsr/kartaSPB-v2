import { layerGroups, userVisibleLayers } from "../map/layerRegistry";
import { orderedGroups } from "../map/layerRegistryHelpers";
import type { MapRequestState } from "../map/mapTypes";
import type { CSSProperties } from "react";
import type { LegendDefinition } from "../map/layerContract";
import type { MapPerformanceProfile } from "../map/performanceProfile";
import { minimumZoomForLayer } from "../map/performanceProfile";

export type LayerControlProps = {
  visibleLayerIds: ReadonlySet<string>;
  zoom: number;
  requestState: MapRequestState;
  onToggle: (layerId: string) => void;
  performanceProfile?: MapPerformanceProfile;
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

const legendStyle = (legend: LegendDefinition): CSSProperties => {
  if (legend.kind === "raster-gradient") {
    return { background: `linear-gradient(90deg, ${legend.colors.join(", ")})` };
  }
  return {
    backgroundColor: legend.color,
    borderColor:
      legend.kind === "point" || legend.kind === "fill" ? legend.outlineColor : undefined,
  };
};

export function LayerControl({
  visibleLayerIds,
  zoom,
  requestState,
  onToggle,
  performanceProfile = "balanced",
}: LayerControlProps) {
  return (
    <section className="layer-control" aria-labelledby="layers-heading">
      <div className="layer-control__heading">
        <p className="section-label" id="layers-heading">
          Слои
        </p>
        <span>z{zoom.toFixed(1)}</span>
      </div>
      <div className="layer-control__list">
        {orderedGroups(layerGroups, userVisibleLayers).filter(({ layers }) => layers.length > 0).map(({ group, layers }) => (
          <section className="layer-control__group" aria-labelledby={`layer-group-${group.id}`} key={group.id}>
            <p id={`layer-group-${group.id}`} className="layer-control__group-label">
              {group.label}
            </p>
            {layers.map((layer) => {
              const minZoom = minimumZoomForLayer(layer, performanceProfile);
              const belowMinZoom = zoom < minZoom;
              const enabled = visibleLayerIds.has(layer.id);
              const status = layerStatus(layer.id, enabled, belowMinZoom, requestState);
              return (
                <label
                  className={belowMinZoom ? "layer-toggle layer-toggle--muted" : "layer-toggle"}
                  key={layer.id}
                >
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={() => onToggle(layer.id)}
                  />
                  <span
                    className={`layer-swatch layer-swatch--${layer.legend.kind}`}
                    style={legendStyle(layer.legend)}
                    aria-hidden="true"
                  />
                  <span>{layer.label}</span>
                  <small>{belowMinZoom ? `с z${minZoom}` : status}</small>
                </label>
              );
            })}
          </section>
        ))}
      </div>
    </section>
  );
}
