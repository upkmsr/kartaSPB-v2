import type {
  FilterSpecification,
  GeoJSONSourceSpecification,
  Map as MapLibreMap,
  RasterSourceSpecification,
  VectorSourceSpecification,
} from "maplibre-gl";
import type { LayerDefinition, LayerSource, RenderDefinition } from "./layerContract";
import type { CatalogFeatureCollection } from "./mapTypes";
import { CATALOG_SOURCE_ID, installCatalogSelectionLayers } from "./catalogLayerDriver";
import {
  catalogFeatureFilter,
  geometryFilter,
  orderedRenderDefinitionsFor,
  partitionLayersByDriver,
} from "./layerRegistryHelpers";

export type LayerRuntimeContext = {
  catalogData: CatalogFeatureCollection;
  selectedCanonicalId: string | null;
};

type SourceDriver = {
  installSource: (
    map: MapLibreMap,
    source: LayerSource,
    context: LayerRuntimeContext,
  ) => void;
};

const addGeoJsonSource = (map: MapLibreMap, sourceId: string, data: string): void => {
  if (!map.getSource(sourceId)) map.addSource(sourceId, { type: "geojson", data });
};

const addVectorSource = (
  map: MapLibreMap,
  sourceId: string,
  tiles: readonly string[],
  attribution?: string,
): void => {
  if (map.getSource(sourceId)) return;
  const specification: VectorSourceSpecification = {
    type: "vector",
    tiles: [...tiles],
    ...(attribution ? { attribution } : {}),
  };
  map.addSource(sourceId, specification);
};

const addRasterSource = (
  map: MapLibreMap,
  sourceId: string,
  tiles: readonly string[],
  tileSize = 256,
  attribution?: string,
): void => {
  if (map.getSource(sourceId)) return;
  const specification: RasterSourceSpecification = {
    type: "raster",
    tiles: [...tiles],
    tileSize,
    ...(attribution ? { attribution } : {}),
  };
  map.addSource(sourceId, specification);
};

const sourceDrivers: Record<LayerSource["type"], SourceDriver> = {
  catalog: {
    installSource: (map, source, context) => {
      if (source.type !== "catalog" || map.getSource(source.sourceId)) return;
      const specification: GeoJSONSourceSpecification = {
        type: "geojson",
        data: context.catalogData,
      };
      map.addSource(source.sourceId, specification);
    },
  },
  geojson: {
    installSource: (map, source) => {
      if (source.type === "geojson") addGeoJsonSource(map, source.sourceId, source.dataUrl);
    },
  },
  "vector-tile": {
    installSource: (map, source) => {
      if (source.type === "vector-tile") {
        addVectorSource(map, source.sourceId, source.tiles, source.attribution);
      }
    },
  },
  "raster-tile": {
    installSource: (map, source) => {
      if (source.type === "raster-tile") {
        addRasterSource(map, source.sourceId, source.tiles, source.tileSize, source.attribution);
      }
    },
  },
  derived: {
    installSource: (map, source) => {
      if (source.type !== "derived") return;
      if (source.delivery.type === "geojson") {
        addGeoJsonSource(map, source.sourceId, source.delivery.dataUrl);
      } else if (source.delivery.type === "vector-tile") {
        addVectorSource(map, source.sourceId, source.delivery.tiles);
      } else {
        addRasterSource(
          map,
          source.sourceId,
          source.delivery.tiles,
          source.delivery.tileSize,
        );
      }
    },
  },
};

const definitionFilter = (
  layer: LayerDefinition,
  definition: RenderDefinition,
): FilterSpecification | undefined => {
  const filters: FilterSpecification[] = [];
  if (layer.source.type === "catalog" && definition.type !== "raster") {
    const geometry = definition.type === "symbol" ? definition.geometry : definition.geometry;
    if (geometry) filters.push(catalogFeatureFilter(layer.source.categoryKey, geometry));
  } else if (definition.type !== "raster" && definition.geometry) {
    filters.push(geometryFilter(definition.geometry));
  }
  if (definition.filter) filters.push(definition.filter);
  if (filters.length === 0) return undefined;
  return filters.length === 1 ? filters[0] : (["all", ...filters] as FilterSpecification);
};

const installRenderDefinition = (
  map: MapLibreMap,
  layer: LayerDefinition,
  definition: RenderDefinition,
  visible: boolean,
): void => {
  if (map.getLayer(definition.id)) return;
  const common = {
    id: definition.id,
    source: layer.source.sourceId,
    minzoom: layer.minZoom,
    ...(layer.maxZoom === undefined ? {} : { maxzoom: layer.maxZoom }),
    ...(definition.sourceLayer === undefined ? {} : { "source-layer": definition.sourceLayer }),
    ...(definitionFilter(layer, definition) === undefined
      ? {}
      : { filter: definitionFilter(layer, definition) }),
  };
  const visibility = visible ? "visible" : "none";
  if (definition.type === "circle") {
    map.addLayer({
      ...common,
      type: "circle",
      layout: { ...definition.layout, visibility },
      paint: definition.paint,
    });
  } else if (definition.type === "fill") {
    map.addLayer({
      ...common,
      type: "fill",
      layout: { ...definition.layout, visibility },
      paint: definition.paint,
    });
  } else if (definition.type === "line") {
    map.addLayer({
      ...common,
      type: "line",
      layout: { ...definition.layout, visibility },
      paint: definition.paint,
    });
  } else if (definition.type === "symbol") {
    map.addLayer({
      ...common,
      type: "symbol",
      layout: { ...definition.layout, visibility },
      paint: definition.paint,
    });
  } else {
    map.addLayer({
      ...common,
      type: "raster",
      layout: { ...definition.layout, visibility },
      paint: definition.paint,
    });
  }
};

export const installRegisteredLayers = (
  map: MapLibreMap,
  registry: readonly LayerDefinition[],
  visibleLayerIds: ReadonlySet<string>,
  context: LayerRuntimeContext,
): void => {
  for (const [sourceType, layers] of partitionLayersByDriver(registry)) {
    const driver = sourceDrivers[sourceType];
    for (const layer of layers) driver.installSource(map, layer.source, context);
  }
  for (const { logicalLayer, definition } of orderedRenderDefinitionsFor(registry)) {
    installRenderDefinition(map, logicalLayer, definition, visibleLayerIds.has(logicalLayer.id));
  }
  for (const layer of registry) {
    for (const mapping of layer.opacity.applyTo) {
      if (map.getLayer(mapping.renderLayerId)) {
        map.setPaintProperty(mapping.renderLayerId, mapping.paintProperty, layer.opacity.default);
      }
    }
  }
  if (registry.some((layer) => layer.source.sourceId === CATALOG_SOURCE_ID)) {
    installCatalogSelectionLayers(map, context.selectedCanonicalId);
  }
};

export const setRegisteredLayerVisibility = (
  map: MapLibreMap,
  registry: readonly LayerDefinition[],
  visibleLayerIds: ReadonlySet<string>,
): void => {
  for (const layer of registry) {
    const visibility = visibleLayerIds.has(layer.id) ? "visible" : "none";
    for (const definition of layer.renderDefinitions) {
      if (map.getLayer(definition.id)) {
        map.setLayoutProperty(definition.id, "visibility", visibility);
      }
    }
  }
};
