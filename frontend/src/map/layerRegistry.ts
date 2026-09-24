import type { ExpressionSpecification } from "maplibre-gl";
import type { LogicalLayer, RenderGeometry } from "./mapTypes";

const institutionRender = (id: string, color: string): LogicalLayer["renderDefinitions"] => [
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

export const layerRegistry: readonly LogicalLayer[] = [
  {
    id: "water",
    categoryKey: "nature.water",
    label: "Вода",
    defaultVisible: true,
    minZoom: 9,
    interactive: true,
    renderDefinitions: [
      {
        id: "water-fill",
        order: 10,
        type: "fill",
        geometry: "polygon",
        paint: { "fill-color": "#2f86b3", "fill-opacity": 0.42 },
      },
    ],
  },
  {
    id: "park",
    categoryKey: "nature.park",
    label: "Парки",
    defaultVisible: true,
    minZoom: 10,
    interactive: true,
    renderDefinitions: [
      {
        id: "park-fill",
        order: 20,
        type: "fill",
        geometry: "polygon",
        paint: { "fill-color": "#5b9f57", "fill-opacity": 0.34 },
      },
      {
        id: "park-outline",
        order: 25,
        type: "line",
        geometry: "polygon",
        paint: { "line-color": "#83c77a", "line-width": 1, "line-opacity": 0.75 },
      },
    ],
  },
  {
    id: "school",
    categoryKey: "education.school",
    label: "Школы",
    defaultVisible: true,
    minZoom: 13,
    interactive: true,
    renderDefinitions: institutionRender("school", "#e5cf59"),
  },
  {
    id: "kindergarten",
    categoryKey: "education.kindergarten",
    label: "Детские сады",
    defaultVisible: true,
    minZoom: 13,
    interactive: true,
    renderDefinitions: institutionRender("kindergarten", "#f09b55"),
  },
  {
    id: "pharmacy",
    categoryKey: "healthcare.pharmacy",
    label: "Аптеки",
    defaultVisible: true,
    minZoom: 14,
    interactive: true,
    renderDefinitions: institutionRender("pharmacy", "#ee77b7"),
  },
  {
    id: "hospital",
    categoryKey: "healthcare.hospital",
    label: "Больницы",
    defaultVisible: true,
    minZoom: 12,
    interactive: true,
    renderDefinitions: institutionRender("hospital", "#ff6f62"),
  },
  {
    id: "clinic",
    categoryKey: "healthcare.clinic",
    label: "Клиники",
    defaultVisible: true,
    minZoom: 13,
    interactive: true,
    renderDefinitions: institutionRender("clinic", "#5fd2c8"),
  },
  {
    id: "road",
    categoryKey: "transport.road",
    label: "Дороги",
    defaultVisible: true,
    minZoom: 16,
    interactive: true,
    renderDefinitions: [
      {
        id: "road-line",
        order: 40,
        type: "line",
        geometry: "line",
        paint: {
          "line-color": "#8f9da3",
          "line-width": ["interpolate", ["linear"], ["zoom"], 16, 1.1, 19, 3.5],
          "line-opacity": 0.78,
        },
      },
    ],
  },
  {
    id: "boundary",
    categoryKey: "boundary.administrative",
    label: "Адм. границы",
    defaultVisible: false,
    minZoom: 10,
    interactive: true,
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
  },
  {
    id: "stop",
    categoryKey: "transport.stop",
    label: "Остановки",
    defaultVisible: true,
    minZoom: 14,
    interactive: true,
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
  },
] as const;

export const defaultVisibleLayerIds = (): Set<string> =>
  new Set(layerRegistry.filter((layer) => layer.defaultVisible).map((layer) => layer.id));

export const activeCategoryKeys = (visibleLayerIds: ReadonlySet<string>, zoom: number): string[] =>
  Array.from(
    new Set(
      layerRegistry
        .filter((layer) => visibleLayerIds.has(layer.id) && zoom >= layer.minZoom)
        .map((layer) => layer.categoryKey),
    ),
  );

export const renderLayerIds = layerRegistry.flatMap((layer) =>
  layer.renderDefinitions.map((definition) => definition.id),
);

export const orderedRenderDefinitions = layerRegistry
  .flatMap((logicalLayer) =>
    logicalLayer.renderDefinitions.map((definition) => ({ logicalLayer, definition })),
  )
  .sort((left, right) => left.definition.order - right.definition.order);

export const interactiveRenderLayerIds = layerRegistry
  .filter((layer) => layer.interactive)
  .flatMap((layer) => layer.renderDefinitions.map((definition) => definition.id));

export const geometryFilter = (geometry: RenderGeometry): ExpressionSpecification => [
  "==",
  ["geometry-type"],
  geometry === "point" ? "Point" : geometry === "line" ? "LineString" : "Polygon",
];

export const categoryFilter = (
  categoryKey: string,
  geometry: RenderGeometry,
): ExpressionSpecification => [
  "all",
  ["in", categoryKey, ["get", "categories"]],
  geometryFilter(geometry),
];

export const categoryLabel = (categoryKey: string): string =>
  layerRegistry.find((layer) => layer.categoryKey === categoryKey)?.label ?? categoryKey;
