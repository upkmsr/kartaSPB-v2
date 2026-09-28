import type { Map as MapLibreMap, StyleSpecification } from "maplibre-gl";

type BasemapStyleTarget = Pick<MapLibreMap, "getStyle" | "setLayoutProperty">;
type StyleLayer = StyleSpecification["layers"][number];
type SymbolStyleLayer = Extract<StyleLayer, { type: "symbol" }>;

const roadArrowContracts = [
  { id: "road_oneway", oneway: 1, originalRotation: 0, alignedRotation: 90 },
  {
    id: "road_oneway_opposite",
    oneway: -1,
    originalRotation: 180,
    alignedRotation: 270,
  },
] as const;

const hasOnewayFilter = (layer: SymbolStyleLayer, oneway: 1 | -1): boolean => {
  const filter = layer.filter;
  return (
    Array.isArray(filter) &&
    filter[0] === "==" &&
    Array.isArray(filter[1]) &&
    filter[1][0] === "get" &&
    filter[1][1] === "oneway" &&
    filter[2] === oneway
  );
};

export const alignOpenFreeMapRoadArrows = (map: BasemapStyleTarget): void => {
  const layers = map.getStyle().layers;
  for (const contract of roadArrowContracts) {
    const layer = layers.find((candidate) => candidate.id === contract.id);
    if (
      !layer ||
      layer.type !== "symbol" ||
      layer.source !== "openmaptiles" ||
      layer["source-layer"] !== "transportation" ||
      layer.layout?.["symbol-placement"] !== "line" ||
      layer.layout["icon-image"] !== "oneway" ||
      layer.layout["icon-rotation-alignment"] !== "map" ||
      !hasOnewayFilter(layer, contract.oneway)
    ) {
      continue;
    }

    const currentRotation = layer.layout["icon-rotate"];
    if (
      currentRotation !== contract.originalRotation &&
      currentRotation !== contract.alignedRotation
    ) {
      continue;
    }
    map.setLayoutProperty(contract.id, "icon-rotate", contract.alignedRotation);
  }
};
