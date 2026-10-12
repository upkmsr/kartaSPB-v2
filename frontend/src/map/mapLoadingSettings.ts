import { defaultVisibleLayerIds, layerRegistry } from "./layerRegistry";
import type { HeatmapResolutionMode } from "./heatmapResolution";
import type { MapPerformanceProfile } from "./performanceProfile";

export const MAP_LOADING_SETTINGS_VERSION = 3 as const;
export const MAP_LOADING_SETTINGS_STORAGE_KEY = "kartaspb.map-loading-settings";

export type MapLoadingSettings = {
  version: typeof MAP_LOADING_SETTINGS_VERSION;
  autoLoad: boolean;
  visibleLayerIds: Set<string>;
  performanceProfile: MapPerformanceProfile;
  analysisDetail: HeatmapResolutionMode;
};

type StoredMapLoadingSettings = {
  version: typeof MAP_LOADING_SETTINGS_VERSION;
  autoLoad: boolean;
  visibleLayerIds: string[];
  knownLayerIds: string[];
  performanceProfile: MapPerformanceProfile;
  analysisDetail: HeatmapResolutionMode;
};

type LegacyMapLoadingSettings = {
  version: 1 | 2;
  autoLoad: boolean;
  visibleLayerIds: string[];
  knownLayerIds: string[];
};

type StorageLike = Pick<Storage, "getItem" | "setItem">;

export const defaultMapLoadingSettings = (): MapLoadingSettings => ({
  version: MAP_LOADING_SETTINGS_VERSION,
  autoLoad: true,
  visibleLayerIds: defaultVisibleLayerIds(),
  performanceProfile: "balanced",
  analysisDetail: "auto",
});

const isStringArray = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((item) => typeof item === "string");

const availableStorage = (): StorageLike | null => {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
};

export const loadMapLoadingSettings = (
  storage: StorageLike | null = availableStorage(),
): MapLoadingSettings => {
  const defaults = defaultMapLoadingSettings();
  if (storage === null) return defaults;

  try {
    const raw = storage.getItem(MAP_LOADING_SETTINGS_STORAGE_KEY);
    if (raw === null) return defaults;
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed !== "object" ||
      parsed === null ||
      !("version" in parsed) ||
      ![1, 2, MAP_LOADING_SETTINGS_VERSION].includes(Number(parsed.version)) ||
      !("autoLoad" in parsed) ||
      typeof parsed.autoLoad !== "boolean" ||
      !("visibleLayerIds" in parsed) ||
      !isStringArray(parsed.visibleLayerIds) ||
      !("knownLayerIds" in parsed) ||
      !isStringArray(parsed.knownLayerIds)
    ) {
      return defaults;
    }

    const stored = parsed as StoredMapLoadingSettings | LegacyMapLoadingSettings;
    const previouslyKnown = new Set(stored.knownLayerIds);
    const previouslyVisible = new Set(stored.visibleLayerIds);
    const visibleLayerIds = new Set<string>();
    for (const layer of layerRegistry) {
      if (layer.id === "analysis-grid") continue;
      if (stored.version === 1 && layer.id === "road") continue;
      if (previouslyKnown.has(layer.id) ? previouslyVisible.has(layer.id) : layer.defaultVisible) {
        visibleLayerIds.add(layer.id);
      }
    }
    const performanceProfile = stored.version === MAP_LOADING_SETTINGS_VERSION
      ? stored.performanceProfile
      : defaults.performanceProfile;
    const analysisDetail = stored.version === MAP_LOADING_SETTINGS_VERSION
      ? stored.analysisDetail
      : defaults.analysisDetail;
    if (!["economy", "balanced", "detailed"].includes(performanceProfile)) return defaults;
    if (!["auto", "200m", "50m"].includes(analysisDetail)) return defaults;
    return {
      version: MAP_LOADING_SETTINGS_VERSION,
      autoLoad: stored.autoLoad,
      visibleLayerIds,
      performanceProfile,
      analysisDetail,
    };
  } catch {
    return defaults;
  }
};

export const saveMapLoadingSettings = (
  settings: MapLoadingSettings,
  storage: StorageLike | null = availableStorage(),
): void => {
  if (storage === null) return;
  const payload: StoredMapLoadingSettings = {
    version: MAP_LOADING_SETTINGS_VERSION,
    autoLoad: settings.autoLoad,
    visibleLayerIds: layerRegistry
      .filter((layer) => settings.visibleLayerIds.has(layer.id))
      .map((layer) => layer.id),
    knownLayerIds: layerRegistry.map((layer) => layer.id),
    performanceProfile: settings.performanceProfile,
    analysisDetail: settings.analysisDetail,
  };
  try {
    storage.setItem(MAP_LOADING_SETTINGS_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // Storage can be unavailable in privacy modes. Runtime defaults remain usable.
  }
};
