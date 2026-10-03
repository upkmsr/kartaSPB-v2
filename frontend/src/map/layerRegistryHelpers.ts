import type { ExpressionSpecification } from "maplibre-gl";
import type {
  LayerDefinition,
  LayerGroup,
  LayerSource,
  MapSelection,
  RenderGeometry,
  SelectionStrategy,
} from "./layerContract";

export type OrderedRenderDefinition = {
  logicalLayer: LayerDefinition;
  definition: LayerDefinition["renderDefinitions"][number];
};

export type InteractionEntry = {
  logicalLayerId: string;
  selection: SelectionStrategy;
};

export type InteractionIndex = ReadonlyMap<string, InteractionEntry>;

export const enabledLayers = (
  registry: readonly LayerDefinition[],
  enabledIds: ReadonlySet<string>,
): LayerDefinition[] => registry.filter((layer) => enabledIds.has(layer.id));

export const loadableLayers = (
  registry: readonly LayerDefinition[],
  enabledIds: ReadonlySet<string>,
  zoom: number,
): LayerDefinition[] =>
  enabledLayers(registry, enabledIds).filter(
    (layer) => zoom >= layer.minZoom && (layer.maxZoom === undefined || zoom <= layer.maxZoom),
  );

export const waitingLayers = (
  registry: readonly LayerDefinition[],
  enabledIds: ReadonlySet<string>,
  zoom: number,
): LayerDefinition[] => {
  const loadableIds = new Set(loadableLayers(registry, enabledIds, zoom).map((layer) => layer.id));
  return enabledLayers(registry, enabledIds).filter((layer) => !loadableIds.has(layer.id));
};

export const s6ViewportLayers = (registry: readonly LayerDefinition[]): LayerDefinition[] =>
  registry.filter((layer) => layer.source.loadParticipation === "s6-viewport");

export const catalogCategoryKeys = (
  registry: readonly LayerDefinition[],
  enabledIds: ReadonlySet<string>,
  zoom?: number,
): string[] => {
  const candidates =
    zoom === undefined
      ? enabledLayers(registry, enabledIds)
      : loadableLayers(registry, enabledIds, zoom);
  return Array.from(
    new Set(
      candidates.flatMap((layer) =>
        layer.source.type === "catalog" ? [layer.source.categoryKey] : [],
      ),
    ),
  );
};

export const defaultLayerIds = (registry: readonly LayerDefinition[]): Set<string> =>
  new Set(registry.filter((layer) => layer.defaultVisible).map((layer) => layer.id));

export const orderedRenderDefinitionsFor = (
  registry: readonly LayerDefinition[],
): OrderedRenderDefinition[] =>
  registry
    .flatMap((logicalLayer) =>
      logicalLayer.renderDefinitions.map((definition) => ({ logicalLayer, definition })),
    )
    .sort((left, right) => left.definition.order - right.definition.order);

export const partitionLayersByDriver = (
  registry: readonly LayerDefinition[],
): Map<LayerSource["type"], LayerDefinition[]> => {
  const result = new Map<LayerSource["type"], LayerDefinition[]>();
  for (const layer of registry) {
    const partition = result.get(layer.source.type) ?? [];
    partition.push(layer);
    result.set(layer.source.type, partition);
  }
  return result;
};

export const buildInteractionIndex = (
  registry: readonly LayerDefinition[],
): Map<string, InteractionEntry> => {
  const index = new Map<string, InteractionEntry>();
  for (const layer of registry) {
    if (layer.selection.kind === "none") continue;
    for (const definition of layer.renderDefinitions) {
      if (index.has(definition.id)) {
        throw new Error(`Duplicate interactive render layer ID: ${definition.id}`);
      }
      index.set(definition.id, { logicalLayerId: layer.id, selection: layer.selection });
    }
  }
  return index;
};

type SelectableFeature = {
  id?: string | number;
  properties?: Record<string, unknown> | null;
};

export const resolveMapSelection = (
  renderLayerId: string,
  feature: SelectableFeature,
  interactionIndex: InteractionIndex,
): MapSelection | null => {
  const entry = interactionIndex.get(renderLayerId);
  if (!entry || entry.selection.kind === "none") return null;
  if (entry.selection.kind === "canonical-object") {
    const objectId =
      feature.properties?.representative_canonical_id ?? feature.properties?.canonical_id;
    return typeof objectId === "string" ? { kind: "canonical-object", objectId } : null;
  }
  const configuredId = entry.selection.idProperty
    ? feature.properties?.[entry.selection.idProperty]
    : undefined;
  const featureId = configuredId ?? feature.id;
  return typeof featureId === "string" || typeof featureId === "number"
    ? { kind: "layer-feature", layerId: entry.logicalLayerId, featureId: String(featureId) }
    : null;
};

export const geometryFilter = (geometry: RenderGeometry): ExpressionSpecification => [
  "==",
  ["geometry-type"],
  geometry === "point" ? "Point" : geometry === "line" ? "LineString" : "Polygon",
];

export const catalogFeatureFilter = (
  categoryKey: string,
  geometry: RenderGeometry,
): ExpressionSpecification => [
  "all",
  ["in", categoryKey, ["get", "categories"]],
  geometryFilter(geometry),
];

export const orderedGroups = (
  groups: readonly LayerGroup[],
  registry: readonly LayerDefinition[],
): Array<{ group: LayerGroup; layers: LayerDefinition[] }> =>
  [...groups]
    .sort((left, right) => left.order - right.order)
    .map((group) => ({ group, layers: registry.filter((layer) => layer.groupId === group.id) }));

export const validateLayerRegistry = (
  registry: readonly LayerDefinition[],
  groups: readonly LayerGroup[],
): string[] => {
  const errors: string[] = [];
  const groupIds = new Set(groups.map((group) => group.id));
  const layerIds = new Set<string>();
  const renderIds = new Set<string>();

  for (const layer of registry) {
    if (!layer.id.trim()) errors.push("Layer ID must not be empty");
    if (layerIds.has(layer.id)) errors.push(`Duplicate logical layer ID: ${layer.id}`);
    layerIds.add(layer.id);
    if (!groupIds.has(layer.groupId)) errors.push(`Unknown group for ${layer.id}: ${layer.groupId}`);
    if (layer.minZoom < 0 || layer.minZoom > 24) errors.push(`Invalid minZoom for ${layer.id}`);
    if (
      layer.maxZoom !== undefined &&
      (layer.maxZoom < 0 || layer.maxZoom > 24 || layer.maxZoom <= layer.minZoom)
    ) {
      errors.push(`Invalid maxZoom for ${layer.id}`);
    }
    if (layer.opacity.default < 0 || layer.opacity.default > 1) {
      errors.push(`Invalid opacity for ${layer.id}`);
    }
    if (layer.renderDefinitions.length === 0) errors.push(`Missing render definitions for ${layer.id}`);
    for (const definition of layer.renderDefinitions) {
      if (renderIds.has(definition.id)) errors.push(`Duplicate render layer ID: ${definition.id}`);
      renderIds.add(definition.id);
    }
    const ownRenderIds = new Set(layer.renderDefinitions.map((definition) => definition.id));
    for (const mapping of layer.opacity.applyTo) {
      if (!ownRenderIds.has(mapping.renderLayerId)) {
        errors.push(`Unknown opacity render layer for ${layer.id}: ${mapping.renderLayerId}`);
      }
    }

    const source = layer.source;
    if (!source.sourceId.trim()) errors.push(`Missing source configuration for ${layer.id}`);
    if (source.type === "catalog") {
      if (!source.categoryKey.trim()) errors.push(`Missing catalog category for ${layer.id}`);
      if (
        layer.loadingStrategy !== "viewport" ||
        source.loadParticipation !== "s6-viewport" ||
        source.districtHandling !== "catalog-filter"
      ) {
        errors.push(`Invalid catalog source/loading strategy for ${layer.id}`);
      }
      if (layer.layerClass !== "canonical-object" || layer.selection.kind !== "canonical-object") {
        errors.push(`Invalid catalog selection semantics for ${layer.id}`);
      }
    } else if (source.type === "geojson") {
      if (!source.dataUrl.trim()) errors.push(`Missing GeoJSON URL for ${layer.id}`);
      if (layer.loadingStrategy === "tiles" || source.loadParticipation === "s6-viewport") {
        errors.push(`Invalid GeoJSON source/loading strategy for ${layer.id}`);
      }
    } else if (source.type === "vector-tile" || source.type === "raster-tile") {
      if (source.tiles.length === 0 || source.tiles.some((tile) => !tile.trim())) {
        errors.push(`Missing tile source configuration for ${layer.id}`);
      }
      if (layer.loadingStrategy !== "tiles" || source.loadParticipation !== "maplibre-native") {
        errors.push(`Invalid tile source/loading strategy for ${layer.id}`);
      }
      if (
        source.type === "vector-tile" &&
        layer.renderDefinitions.some((definition) => definition.sourceLayer === undefined)
      ) {
        errors.push(`Vector tile render layer requires sourceLayer for ${layer.id}`);
      }
    } else {
      const deliveryConfigured =
        source.delivery.type === "geojson"
          ? source.delivery.dataUrl.trim().length > 0
          : source.delivery.tiles.length > 0;
      if (!deliveryConfigured) errors.push(`Missing derived source configuration for ${layer.id}`);
      if (layer.layerClass !== "derived-analysis") {
        errors.push(`Derived source requires derived-analysis class for ${layer.id}`);
      }
      const tileDelivery = source.delivery.type !== "geojson";
      if (
        (tileDelivery &&
          (layer.loadingStrategy !== "tiles" || source.loadParticipation !== "maplibre-native")) ||
        (!tileDelivery &&
          (layer.loadingStrategy === "tiles" || source.loadParticipation === "s6-viewport"))
      ) {
        errors.push(`Invalid derived source/loading strategy for ${layer.id}`);
      }
    }

    if (layer.layerClass === "temporal-vector" && layer.time.kind === "none") {
      errors.push(`Temporal layer requires time metadata: ${layer.id}`);
    }
    if (layer.layerClass !== "temporal-vector" && layer.time.kind !== "none") {
      errors.push(`Non-temporal layer has temporal metadata: ${layer.id}`);
    }
    if (layer.layerClass === "raster" && layer.selection.kind !== "none") {
      errors.push(`Raster layer selection must be none: ${layer.id}`);
    }
    const rasterDelivery =
      source.type === "raster-tile" ||
      (source.type === "derived" && source.delivery.type === "raster-tile");
    if (layer.layerClass === "raster" && !rasterDelivery) {
      errors.push(`Raster layer requires raster delivery: ${layer.id}`);
    }
    if (rasterDelivery && layer.renderDefinitions.some((definition) => definition.type !== "raster")) {
      errors.push(`Raster delivery requires raster render definitions: ${layer.id}`);
    }
  }
  return errors;
};

export const assertValidLayerRegistry = (
  registry: readonly LayerDefinition[],
  groups: readonly LayerGroup[],
): void => {
  const errors = validateLayerRegistry(registry, groups);
  if (errors.length > 0) throw new Error(`Invalid layer registry:\n${errors.join("\n")}`);
};
