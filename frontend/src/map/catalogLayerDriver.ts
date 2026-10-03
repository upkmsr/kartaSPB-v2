import type {
  ExpressionSpecification,
  FilterSpecification,
  GeoJSONSource,
  Map as MapLibreMap,
} from "maplibre-gl";
import type { CatalogFeatureCollection } from "./mapTypes";
import type { LayerDefinition } from "./layerContract";
import {
  catalogCategoryKeys,
  enabledLayers,
  geometryFilter,
  loadableLayers,
  s6ViewportLayers,
} from "./layerRegistryHelpers";

export const CATALOG_SOURCE_ID = "catalog-features";

export type CatalogViewportPlan = {
  enabledLayerIds: string[];
  loadableLayerIds: string[];
  categoryKeys: string[];
};

export const planCatalogViewport = (
  registry: readonly LayerDefinition[],
  enabledIds: ReadonlySet<string>,
  zoom: number,
): CatalogViewportPlan => {
  const catalogViewportRegistry = s6ViewportLayers(registry).filter(
    (layer) => layer.source.type === "catalog",
  );
  return {
    enabledLayerIds: enabledLayers(catalogViewportRegistry, enabledIds).map((layer) => layer.id),
    loadableLayerIds: loadableLayers(catalogViewportRegistry, enabledIds, zoom).map(
      (layer) => layer.id,
    ),
    categoryKeys: catalogCategoryKeys(catalogViewportRegistry, enabledIds, zoom),
  };
};

const selectedMembershipFilter = (selectedId: string | null): ExpressionSpecification => [
  "any",
  ["==", ["get", "canonical_id"], selectedId ?? ""],
  ["in", selectedId ?? "", ["get", "member_canonical_ids"]],
];

const selectedFilter = (
  geometry: "point" | "line" | "polygon",
  selectedId: string | null,
): FilterSpecification => [
  "all",
  geometryFilter(geometry),
  selectedMembershipFilter(selectedId),
];

export const setCatalogSourceData = (
  map: MapLibreMap,
  collection: CatalogFeatureCollection,
): void => {
  const source = map.getSource(CATALOG_SOURCE_ID) as GeoJSONSource | undefined;
  if (source) source.setData(collection as Parameters<GeoJSONSource["setData"]>[0]);
};

export const installCatalogSelectionLayers = (
  map: MapLibreMap,
  selectedId: string | null,
): void => {
  if (map.getLayer("selection-fill")) return;
  map.addLayer({
    id: "selection-fill",
    source: CATALOG_SOURCE_ID,
    type: "fill",
    filter: selectedFilter("polygon", selectedId),
    paint: { "fill-color": "#bbff3c", "fill-opacity": 0.42 },
  });
  map.addLayer({
    id: "selection-line",
    source: CATALOG_SOURCE_ID,
    type: "line",
    filter: [
      "all",
      ["any", geometryFilter("line"), geometryFilter("polygon")],
      selectedMembershipFilter(selectedId),
    ],
    paint: { "line-color": "#bbff3c", "line-width": 4, "line-opacity": 1 },
  });
  map.addLayer({
    id: "selection-point",
    source: CATALOG_SOURCE_ID,
    type: "circle",
    filter: selectedFilter("point", selectedId),
    paint: {
      "circle-color": "#bbff3c",
      "circle-radius": 10,
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 2,
    },
  });
};

export const updateCatalogSelection = (
  map: MapLibreMap,
  selectedId: string | null,
): void => {
  if (!map.getLayer("selection-fill")) return;
  map.setFilter("selection-fill", selectedFilter("polygon", selectedId));
  map.setFilter("selection-line", [
    "all",
    ["any", geometryFilter("line"), geometryFilter("polygon")],
    selectedMembershipFilter(selectedId),
  ]);
  map.setFilter("selection-point", selectedFilter("point", selectedId));
};
