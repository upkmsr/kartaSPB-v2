import type { ExpressionSpecification, Map as MapLibreMap } from "maplibre-gl";
import type { PreparedInfluence } from "../api/influence";
import type { IndependentLayerState } from "../analysis/analysisPreferences";
import { factorByMetric, factorRegistry } from "../analysis/factorRegistry";

export const INFLUENCE_SOURCE_ID = "analysis-influence-source";
export const INFLUENCE_SOURCE_LAYER = "analysis_influence";
export const INFLUENCE_MIN_ZOOM = 8;

export type InfluenceRenderState = {
  prepared: PreparedInfluence;
  layers: Record<string, IndependentLayerState>;
  accentedFactorId: string | null;
};

type InfluenceOverlayMap = Pick<
  MapLibreMap,
  | "addLayer"
  | "addSource"
  | "getLayer"
  | "getSource"
  | "removeLayer"
  | "removeSource"
  | "setFilter"
  | "setPaintProperty"
>;

const installedSignatures = new WeakMap<object, string>();

export const influenceLayerId = (factorId: string): string =>
  `analysis-influence-${factorId}`;

export const influenceLayerIds = factorRegistry.map((factor) => influenceLayerId(factor.id));

const opacityForCount = (count: number): number => {
  if (count <= 1) return 0.34;
  return 1 - Math.pow(0.5, 1 / count);
};

const factorOpacity = (
  propertyName: string,
  minimumScore: number,
  maximumOpacity: number,
): ExpressionSpecification => [
  "case",
  [">=", ["get", propertyName], minimumScore],
  [
    "interpolate",
    ["linear"],
    ["get", propertyName],
    minimumScore,
    maximumOpacity * 0.4,
    100,
    maximumOpacity,
  ],
  0,
];

const removeInfluenceOverlay = (map: InfluenceOverlayMap): void => {
  for (const layerId of [...influenceLayerIds].reverse()) {
    if (map.getLayer(layerId)) map.removeLayer(layerId);
  }
  if (map.getSource(INFLUENCE_SOURCE_ID)) map.removeSource(INFLUENCE_SOURCE_ID);
  installedSignatures.delete(map as object);
};

export const updateInfluenceOverlay = (
  map: InfluenceOverlayMap,
  state: InfluenceRenderState | null,
  beforeId?: string,
): void => {
  if (state === null) {
    removeInfluenceOverlay(map);
    return;
  }
  const { prepared, layers, accentedFactorId } = state;
  const enabledChannels = prepared.channels.filter((channel) => {
    const factor = factorByMetric.get(channel.metric_key);
    return factor !== undefined && layers[factor.id]?.enabled;
  });
  if (enabledChannels.length === 0) {
    removeInfluenceOverlay(map);
    return;
  }
  const maxOpacity = opacityForCount(enabledChannels.length);
  const signatureChanged =
    installedSignatures.get(map as object) !== prepared.influence_signature ||
    !map.getSource(INFLUENCE_SOURCE_ID);
  if (signatureChanged) {
    removeInfluenceOverlay(map);
    map.addSource(INFLUENCE_SOURCE_ID, {
      type: "vector",
      tiles: [prepared.tile_url_template],
      minzoom: INFLUENCE_MIN_ZOOM,
      maxzoom: 22,
    });
  }

  for (const channel of enabledChannels) {
    const factor = factorByMetric.get(channel.metric_key)!;
    const layerId = influenceLayerId(factor.id);
    const threshold = layers[factor.id]?.minimumScore ?? 40;
    const muted = accentedFactorId !== null && accentedFactorId !== factor.id;
    const opacity = muted ? Math.min(maxOpacity, 0.045) : maxOpacity;
    if (!map.getLayer(layerId)) {
      map.addLayer(
        {
          id: layerId,
          source: INFLUENCE_SOURCE_ID,
          "source-layer": INFLUENCE_SOURCE_LAYER,
          type: "fill",
          minzoom: INFLUENCE_MIN_ZOOM,
          filter: [">=", ["get", channel.property_name], threshold],
          paint: {
            "fill-color": factor.color,
            "fill-opacity": factorOpacity(channel.property_name, threshold, opacity),
            "fill-antialias": false,
          },
        },
        beforeId && map.getLayer(beforeId) ? beforeId : undefined,
      );
    } else {
      map.setFilter(layerId, [">=", ["get", channel.property_name], threshold]);
      map.setPaintProperty(
        layerId,
        "fill-opacity",
        factorOpacity(channel.property_name, threshold, opacity),
      );
    }
  }

  const enabledLayerIds = new Set(
    enabledChannels.map((channel) => influenceLayerId(factorByMetric.get(channel.metric_key)!.id)),
  );
  for (const layerId of influenceLayerIds) {
    if (!enabledLayerIds.has(layerId) && map.getLayer(layerId)) map.removeLayer(layerId);
  }
  installedSignatures.set(map as object, prepared.influence_signature);
};
