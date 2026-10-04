import type { LayerDefinition, LayerGroup, LegendDefinition } from "./layerContract";
import {
  assertValidLayerRegistry,
  buildInteractionIndex,
  catalogCategoryKeys,
  catalogFeatureFilter,
  defaultLayerIds,
  geometryFilter,
  orderedRenderDefinitionsFor,
  s6ViewportLayers,
} from "./layerRegistryHelpers";

export const layerGroups: readonly LayerGroup[] = [
  { id: "city-objects", label: "Городские объекты", order: 10 },
  { id: "analytics", label: "Аналитика", order: 20 },
] as const;

type CatalogLayerConfig = Pick<
  LayerDefinition,
  "id" | "label" | "defaultVisible" | "minZoom" | "renderDefinitions"
> & {
  categoryKey: string;
  legend: LegendDefinition;
};

const catalogLayer = ({ categoryKey, ...definition }: CatalogLayerConfig): LayerDefinition => ({
  ...definition,
  groupId: "city-objects",
  layerClass: "canonical-object",
  source: {
    type: "catalog",
    sourceId: "catalog-features",
    endpoint: "/api/map/features",
    categoryKey,
    loadParticipation: "s6-viewport",
    districtHandling: "catalog-filter",
  },
  selection: { kind: "canonical-object" },
  loadingStrategy: "viewport",
  time: { kind: "none" },
  opacity: { default: 1, adjustable: false, applyTo: [] },
  provenance: {
    kind: "community",
    sourceLabel: "OpenStreetMap",
    attribution: "© OpenStreetMap contributors",
    sourceUrl: "https://www.openstreetmap.org/copyright",
  },
});

const institutionRender = (
  id: string,
  color: string,
): LayerDefinition["renderDefinitions"] => [
  {
    id: `${id}-fill`,
    order: 30,
    type: "fill",
    geometry: "polygon",
    paint: { "fill-color": color, "fill-opacity": 0.28 },
  },
  {
    id: `${id}-outline`,
    order: 35,
    type: "line",
    geometry: "polygon",
    paint: { "line-color": color, "line-width": 1.4, "line-opacity": 0.9 },
  },
  {
    id: `${id}-point`,
    order: 60,
    type: "circle",
    geometry: "point",
    paint: {
      "circle-color": color,
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 12, 3, 17, 6],
      "circle-stroke-color": "#0b0f10",
      "circle-stroke-width": 1.5,
    },
  },
];

export const layerRegistry: readonly LayerDefinition[] = [
  catalogLayer({
    id: "water",
    categoryKey: "nature.water",
    label: "Вода",
    defaultVisible: true,
    minZoom: 9,
    legend: { kind: "fill", color: "#65ace0", outlineColor: "#65ace0" },
    renderDefinitions: [
      {
        id: "water-fill",
        order: 10,
        type: "fill",
        geometry: "polygon",
        paint: { "fill-color": "#2f86b3", "fill-opacity": 0.62 },
      },
      {
        id: "water-outline",
        order: 15,
        type: "line",
        geometry: "polygon",
        paint: { "line-color": "#65ace0", "line-width": 1.2, "line-opacity": 0.92 },
      },
      {
        id: "water-river-line",
        order: 18,
        type: "line",
        geometry: "line",
        paint: {
          "line-color": "#2f86b3",
          "line-width": ["interpolate", ["linear"], ["zoom"], 9, 2, 12, 8, 16, 18],
          "line-opacity": 0.82,
        },
      },
    ],
  }),
  catalogLayer({
    id: "park",
    categoryKey: "nature.park",
    label: "Парки",
    defaultVisible: true,
    minZoom: 10,
    legend: { kind: "fill", color: "#83c77a", outlineColor: "#83c77a" },
    renderDefinitions: [
      {
        id: "park-fill",
        order: 20,
        type: "fill",
        geometry: "polygon",
        paint: { "fill-color": "#5b9f57", "fill-opacity": 0.52 },
      },
      {
        id: "park-outline",
        order: 25,
        type: "line",
        geometry: "polygon",
        paint: { "line-color": "#83c77a", "line-width": 1, "line-opacity": 0.75 },
      },
    ],
  }),
  catalogLayer({
    id: "school",
    categoryKey: "education.school",
    label: "Школы",
    defaultVisible: true,
    minZoom: 13,
    legend: { kind: "point", color: "#e5cf59" },
    renderDefinitions: institutionRender("school", "#e5cf59"),
  }),
  catalogLayer({
    id: "kindergarten",
    categoryKey: "education.kindergarten",
    label: "Детские сады",
    defaultVisible: true,
    minZoom: 13,
    legend: { kind: "point", color: "#f09b55" },
    renderDefinitions: institutionRender("kindergarten", "#f09b55"),
  }),
  catalogLayer({
    id: "pharmacy",
    categoryKey: "healthcare.pharmacy",
    label: "Аптеки",
    defaultVisible: true,
    minZoom: 14,
    legend: { kind: "point", color: "#ee77b7" },
    renderDefinitions: institutionRender("pharmacy", "#ee77b7"),
  }),
  catalogLayer({
    id: "hospital",
    categoryKey: "healthcare.hospital",
    label: "Больницы",
    defaultVisible: true,
    minZoom: 12,
    legend: { kind: "point", color: "#ff6f62" },
    renderDefinitions: institutionRender("hospital", "#ff6f62"),
  }),
  catalogLayer({
    id: "clinic",
    categoryKey: "healthcare.clinic",
    label: "Клиники",
    defaultVisible: true,
    minZoom: 13,
    legend: { kind: "point", color: "#5fd2c8" },
    renderDefinitions: institutionRender("clinic", "#5fd2c8"),
  }),
  catalogLayer({
    id: "road",
    categoryKey: "transport.road",
    label: "Дороги",
    defaultVisible: true,
    minZoom: 16,
    legend: { kind: "line", color: "#ffb347" },
    renderDefinitions: [
      {
        id: "road-line",
        order: 40,
        type: "line",
        geometry: "line",
        paint: {
          "line-color": "#ffb347",
          "line-width": ["interpolate", ["linear"], ["zoom"], 16, 2.4, 19, 6],
          "line-opacity": 0.96,
        },
      },
    ],
  }),
  catalogLayer({
    id: "boundary",
    categoryKey: "boundary.administrative",
    label: "Адм. границы",
    defaultVisible: false,
    minZoom: 10,
    legend: { kind: "line", color: "#be8cff", dashed: true },
    renderDefinitions: [
      {
        id: "boundary-line",
        order: 50,
        type: "line",
        geometry: "polygon",
        paint: {
          "line-color": "#be8cff",
          "line-width": 1.6,
          "line-dasharray": [3, 2],
          "line-opacity": 0.9,
        },
      },
    ],
  }),
  catalogLayer({
    id: "stop",
    categoryKey: "transport.stop",
    label: "Остановки",
    defaultVisible: true,
    minZoom: 14,
    legend: { kind: "point", color: "#65ace0", outlineColor: "#dff0ff" },
    renderDefinitions: [
      {
        id: "stop-point",
        order: 70,
        type: "circle",
        geometry: "point",
        paint: {
          "circle-color": "#8cc8ff",
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 14, 2.5, 18, 5],
          "circle-stroke-color": "#dff0ff",
          "circle-stroke-width": 1,
        },
      },
    ],
  }),
  {
    id: "analysis-grid",
    label: "Аналитическая сетка",
    groupId: "analytics",
    layerClass: "derived-analysis",
    source: {
      type: "derived",
      sourceId: "analysis-grid-source",
      delivery: {
        type: "vector-tile",
        tiles: ["/api/analysis/grid/tiles/{z}/{x}/{y}.mvt"],
      },
      loadParticipation: "maplibre-native",
      districtHandling: "ignored",
    },
    defaultVisible: false,
    minZoom: 11,
    selection: { kind: "none" },
    loadingStrategy: "tiles",
    time: { kind: "none" },
    legend: { kind: "fill", color: "#c8d3d8", outlineColor: "#dce5e8" },
    opacity: { default: 1, adjustable: false, applyTo: [] },
    provenance: {
      kind: "internal",
      sourceLabel: "KARTASPB deterministic analysis grid",
    },
    renderDefinitions: [
      {
        id: "analysis-grid-fill",
        order: 1,
        type: "fill",
        geometry: "polygon",
        sourceLayer: "analysis_grid",
        paint: { "fill-color": "#d5e0e4", "fill-opacity": 0.06 },
      },
      {
        id: "analysis-grid-outline",
        order: 2,
        type: "line",
        geometry: "polygon",
        sourceLayer: "analysis_grid",
        paint: { "line-color": "#cbd8dd", "line-width": 0.65, "line-opacity": 0.52 },
      },
    ],
  },
] as const;

assertValidLayerRegistry(layerRegistry, layerGroups);

export const defaultVisibleLayerIds = (): Set<string> => defaultLayerIds(layerRegistry);

export const activeCategoryKeys = (visibleLayerIds: ReadonlySet<string>, zoom: number): string[] =>
  catalogCategoryKeys(s6ViewportLayers(layerRegistry), visibleLayerIds, zoom);

export const enabledCategoryKeys = (visibleLayerIds: ReadonlySet<string>): string[] =>
  catalogCategoryKeys(layerRegistry, visibleLayerIds);

export const renderLayerIds = layerRegistry.flatMap((layer) =>
  layer.renderDefinitions.map((definition) => definition.id),
);

export const orderedRenderDefinitions = orderedRenderDefinitionsFor(layerRegistry);
export const interactionIndex = buildInteractionIndex(layerRegistry);
export const interactiveRenderLayerIds = [...interactionIndex.keys()];

export { catalogFeatureFilter as categoryFilter, geometryFilter };

export const categoryLabel = (categoryKey: string): string =>
  layerRegistry.find(
    (layer) => layer.source.type === "catalog" && layer.source.categoryKey === categoryKey,
  )?.label ?? categoryKey;
