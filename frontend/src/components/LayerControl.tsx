import { layerRegistry } from "../map/layerRegistry";

export type LayerControlProps = {
  visibleLayerIds: ReadonlySet<string>;
  zoom: number;
  onToggle: (layerId: string) => void;
};

export function LayerControl({ visibleLayerIds, zoom, onToggle }: LayerControlProps) {
  return (
    <section className="layer-control" aria-labelledby="layers-heading">
      <div className="layer-control__heading">
        <p className="section-label" id="layers-heading">
          Слои
        </p>
        <span>z{zoom.toFixed(1)}</span>
      </div>
      <div className="layer-control__list">
        {layerRegistry.map((layer) => {
          const belowMinZoom = zoom < layer.minZoom;
          return (
            <label className={belowMinZoom ? "layer-toggle layer-toggle--muted" : "layer-toggle"} key={layer.id}>
              <input
                type="checkbox"
                checked={visibleLayerIds.has(layer.id)}
                onChange={() => onToggle(layer.id)}
              />
              <span className={`layer-swatch layer-swatch--${layer.id}`} aria-hidden="true" />
              <span>{layer.label}</span>
              {belowMinZoom && <small>с z{layer.minZoom}</small>}
            </label>
          );
        })}
      </div>
    </section>
  );
}
