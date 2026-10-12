import type { LayerDefinition } from "./layerContract";

export type MapPerformanceProfile = "economy" | "balanced" | "detailed";

const zoomOffset: Record<MapPerformanceProfile, number> = {
  economy: 1,
  balanced: 0,
  detailed: -1,
};

export const minimumZoomForLayer = (
  layer: LayerDefinition,
  profile: MapPerformanceProfile,
): number => {
  if (layer.source.type !== "catalog") return layer.minZoom;
  return Math.max(8, Math.min(18, layer.minZoom + zoomOffset[profile]));
};

export const registryForPerformanceProfile = (
  registry: readonly LayerDefinition[],
  profile: MapPerformanceProfile,
): LayerDefinition[] => registry.map((layer) => ({
  ...layer,
  minZoom: minimumZoomForLayer(layer, profile),
}));
