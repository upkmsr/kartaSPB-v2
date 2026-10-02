import { describe, expect, it, vi } from "vitest";
import { defaultVisibleLayerIds, layerRegistry } from "./layerRegistry";
import {
  MAP_LOADING_SETTINGS_STORAGE_KEY,
  defaultMapLoadingSettings,
  loadMapLoadingSettings,
  saveMapLoadingSettings,
} from "./mapLoadingSettings";

const storageWith = (value: string | null) => ({
  getItem: vi.fn(() => value),
  setItem: vi.fn(),
});

describe("map loading settings persistence", () => {
  it("uses current defaults for absent, corrupt, and incompatible payloads", () => {
    expect(loadMapLoadingSettings(storageWith(null))).toEqual(defaultMapLoadingSettings());
    expect(loadMapLoadingSettings(storageWith("{"))).toEqual(defaultMapLoadingSettings());
    expect(
      loadMapLoadingSettings(storageWith(JSON.stringify({ version: 99, autoLoad: false }))),
    ).toEqual(defaultMapLoadingSettings());
  });

  it("restores known choices, ignores removed IDs, and defaults newly introduced layers", () => {
    const knownLayerIds = layerRegistry.slice(0, -1).map((layer) => layer.id);
    const selected = [layerRegistry[0].id, "removed-layer"];
    const loaded = loadMapLoadingSettings(
      storageWith(
        JSON.stringify({
          version: 1,
          autoLoad: false,
          visibleLayerIds: selected,
          knownLayerIds: [...knownLayerIds, "removed-layer"],
        }),
      ),
    );

    expect(loaded.autoLoad).toBe(false);
    expect(loaded.visibleLayerIds.has(layerRegistry[0].id)).toBe(true);
    expect(loaded.visibleLayerIds.has("removed-layer")).toBe(false);
    const newLayer = layerRegistry.at(-1)!;
    expect(loaded.visibleLayerIds.has(newLayer.id)).toBe(newLayer.defaultVisible);
  });

  it("writes a versioned allow-listed payload and tolerates storage failures", () => {
    const storage = storageWith(null);
    saveMapLoadingSettings(
      { version: 1, autoLoad: false, visibleLayerIds: new Set([...defaultVisibleLayerIds(), "x"]) },
      storage,
    );
    expect(storage.setItem).toHaveBeenCalledWith(
      MAP_LOADING_SETTINGS_STORAGE_KEY,
      expect.any(String),
    );
    const payload = JSON.parse(storage.setItem.mock.calls[0][1]);
    expect(payload).toMatchObject({ version: 1, autoLoad: false });
    expect(payload.visibleLayerIds).not.toContain("x");

    expect(() =>
      saveMapLoadingSettings(defaultMapLoadingSettings(), {
        getItem: vi.fn(),
        setItem: vi.fn(() => {
          throw new Error("denied");
        }),
      }),
    ).not.toThrow();
    expect(
      loadMapLoadingSettings({
        getItem: vi.fn(() => {
          throw new Error("denied");
        }),
        setItem: vi.fn(),
      }),
    ).toEqual(defaultMapLoadingSettings());
  });
});
