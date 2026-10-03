import type {
  CircleLayerSpecification,
  FillLayerSpecification,
  FilterSpecification,
  LineLayerSpecification,
  RasterLayerSpecification,
  SymbolLayerSpecification,
} from "maplibre-gl";

export type LayerClass =
  | "canonical-object"
  | "reference-vector"
  | "temporal-vector"
  | "raster"
  | "derived-analysis";

export type LoadingStrategy = "viewport" | "static" | "tiles" | "manual";
export type LoadParticipation = "s6-viewport" | "independent" | "maplibre-native" | "external";
export type DistrictHandling = "catalog-filter" | "ignored" | "source-managed";

type SourceCommon = {
  sourceId: string;
  loadParticipation: LoadParticipation;
  districtHandling: DistrictHandling;
};

export type CatalogLayerSource = SourceCommon & {
  type: "catalog";
  categoryKey: string;
  endpoint: "/api/map/features";
};

export type GeoJsonLayerSource = SourceCommon & {
  type: "geojson";
  dataUrl: string;
};

export type VectorTileLayerSource = SourceCommon & {
  type: "vector-tile";
  tiles: readonly string[];
  attribution?: string;
};

export type RasterTileLayerSource = SourceCommon & {
  type: "raster-tile";
  tiles: readonly string[];
  tileSize?: 256 | 512;
  attribution?: string;
};

export type DerivedDelivery =
  | { type: "geojson"; dataUrl: string }
  | { type: "vector-tile"; tiles: readonly string[] }
  | { type: "raster-tile"; tiles: readonly string[]; tileSize?: 256 | 512 };

export type DerivedLayerSource = SourceCommon & {
  type: "derived";
  delivery: DerivedDelivery;
};

export type LayerSource =
  | CatalogLayerSource
  | GeoJsonLayerSource
  | VectorTileLayerSource
  | RasterTileLayerSource
  | DerivedLayerSource;

export type SelectionStrategy =
  | { kind: "none" }
  | { kind: "canonical-object" }
  | { kind: "layer-feature"; idProperty?: string };

export type MapSelection =
  | { kind: "canonical-object"; objectId: string }
  | { kind: "layer-feature"; layerId: string; featureId: string };

export type TimeAwareness =
  | { kind: "none" }
  | { kind: "snapshot"; property: string }
  | { kind: "range"; startProperty: string; endProperty: string }
  | { kind: "event"; property: string };

export type LegendDefinition =
  | { kind: "point"; color: string; outlineColor?: string; label?: string }
  | { kind: "line"; color: string; secondaryColor?: string; dashed?: boolean; label?: string }
  | { kind: "fill"; color: string; outlineColor?: string; label?: string }
  | { kind: "raster-gradient"; colors: readonly string[]; label?: string };

export type ProvenanceMetadata = {
  kind: "official" | "community" | "derived" | "internal";
  sourceLabel: string;
  attribution?: string;
  sourceUrl?: string;
};

export type OpacityDefinition = {
  default: number;
  adjustable: boolean;
  applyTo: readonly {
    renderLayerId: string;
    paintProperty: "circle-opacity" | "fill-opacity" | "line-opacity" | "raster-opacity";
  }[];
};

export type RenderGeometry = "point" | "line" | "polygon";

type RenderCommon = {
  id: string;
  order: number;
  sourceLayer?: string;
  filter?: FilterSpecification;
};

export type RenderDefinition =
  | (RenderCommon & {
      type: "circle";
      geometry: "point";
      paint: NonNullable<CircleLayerSpecification["paint"]>;
      layout?: NonNullable<CircleLayerSpecification["layout"]>;
    })
  | (RenderCommon & {
      type: "line";
      geometry: "line" | "polygon";
      paint: NonNullable<LineLayerSpecification["paint"]>;
      layout?: NonNullable<LineLayerSpecification["layout"]>;
    })
  | (RenderCommon & {
      type: "fill";
      geometry: "polygon";
      paint: NonNullable<FillLayerSpecification["paint"]>;
      layout?: NonNullable<FillLayerSpecification["layout"]>;
    })
  | (RenderCommon & {
      type: "symbol";
      geometry?: RenderGeometry;
      paint?: NonNullable<SymbolLayerSpecification["paint"]>;
      layout: NonNullable<SymbolLayerSpecification["layout"]>;
    })
  | (RenderCommon & {
      type: "raster";
      paint?: NonNullable<RasterLayerSpecification["paint"]>;
      layout?: NonNullable<RasterLayerSpecification["layout"]>;
    });

export type LayerDefinition = {
  id: string;
  label: string;
  groupId: string;
  layerClass: LayerClass;
  source: LayerSource;
  defaultVisible: boolean;
  minZoom: number;
  maxZoom?: number;
  selection: SelectionStrategy;
  loadingStrategy: LoadingStrategy;
  time: TimeAwareness;
  legend: LegendDefinition;
  opacity: OpacityDefinition;
  provenance?: ProvenanceMetadata;
  renderDefinitions: readonly RenderDefinition[];
};

export type LayerGroup = {
  id: string;
  label: string;
  order: number;
};
