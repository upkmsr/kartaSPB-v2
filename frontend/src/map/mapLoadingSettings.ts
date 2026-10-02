import { defaultVisibleLayerIds, layerRegistry } from "./layerRegistry";

export const MAP_LOADING_SETTINGS_VERSION = 1 as const;
export const MAP_LOADING_SETTINGS_STORAGE_KEY = "kartaspb.map-loading-settings";

export type MapLoadingSettings = {
  version: typeof MAP_LOADING_SETTINGS_VERSION;
  autoLoad: boolean;
  visibleLayerIds: Set<string>;
};

type StoredMapLoadingSettings = {
  version: typeof MAP_LOADING_SETTINGS_VERSION;
  autoLoad: boolean;
  visibleLayerIds: string[];
  knownLayerIds: string[];
};

type StorageLike = Pick<Storage, "getItem" | "setItem">;

export const defaultMapLoadingSettings = (): MapLoadingSettings => ({
  version: MAP_LOADING_SETTINGS_VERSION,
  autoLoad: true,
  visibleLayerIds: defaultVisibleLayerIds(),
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
      parsed.version !== MAP_LOADING_SETTINGS_VERSION ||
      !("autoLoad" in parsed) ||
      typeof parsed.autoLoad !== "boolean" ||
      !("visibleLayerIds" in parsed) ||
      !isStringArray(parsed.visibleLayerIds) ||
      !("knownLayerIds" in parsed) ||
      !isStringArray(parsed.knownLayerIds)
    ) {
      return defaults;
    }

    const stored = parsed as StoredMapLoadingSettings;
    const previouslyKnown = new Set(stored.knownLayerIds);
    const previouslyVisible = new Set(stored.visibleLayerIds);
    const visibleLayerIds = new Set<string>();
    for (const layer of layerRegistry) {
      if (previouslyKnown.has(layer.id) ? previouslyVisible.has(layer.id) : layer.defaultVisible) {
        visibleLayerIds.add(layer.id);
      }
    }
    return { version: MAP_LOADING_SETTINGS_VERSION, autoLoad: stored.autoLoad, visibleLayerIds };
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
  };
  try {
    storage.setItem(MAP_LOADING_SETTINGS_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // Storage can be unavailable in privacy modes. Runtime defaults remain usable.
  }
};
