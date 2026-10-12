import { describe, expect, it, vi } from "vitest";
import {
  ANALYSIS_PREFERENCES_STORAGE_KEY,
  defaultAnalysisPreferences,
  loadAnalysisPreferences,
  saveAnalysisPreferences,
} from "./analysisPreferences";

const storageWith = (value: string | null) => ({
  getItem: vi.fn(() => value),
  setItem: vi.fn(),
});

describe("analysis preferences", () => {
  it("uses safe defaults for missing, invalid, or future payloads", () => {
    expect(loadAnalysisPreferences(storageWith(null))).toEqual(defaultAnalysisPreferences());
    expect(loadAnalysisPreferences(storageWith("{"))).toEqual(defaultAnalysisPreferences());
    expect(loadAnalysisPreferences(storageWith('{"version":99}'))).toEqual(
      defaultAnalysisPreferences(),
    );
  });

  it("restores independent and composite state without mixing them", () => {
    const loaded = loadAnalysisPreferences(storageWith(JSON.stringify({
      version: 1,
      activeAnalysisMode: "composite",
      influenceLayers: {
        school: { enabled: true, minimumScore: 72, showObjects: true },
      },
      scenarioWeights: { "education.school.accessibility_index_v2": 65 },
      scenarioMinScore: 48,
    })));
    expect(loaded.activeAnalysisMode).toBe("composite");
    expect(loaded.influenceLayers.school).toEqual({
      enabled: true,
      minimumScore: 72,
    });
    expect(loaded.scenarioWeights).toEqual({
      "education.school.accessibility_index_v2": 65,
    });
    expect(loaded.scenarioMinScore).toBe(48);
  });

  it("writes one versioned payload and tolerates unavailable storage", () => {
    const storage = storageWith(null);
    saveAnalysisPreferences(defaultAnalysisPreferences(), storage);
    expect(storage.setItem).toHaveBeenCalledWith(
      ANALYSIS_PREFERENCES_STORAGE_KEY,
      expect.stringContaining('"version":1'),
    );
    expect(() => saveAnalysisPreferences(defaultAnalysisPreferences(), {
      getItem: vi.fn(),
      setItem: vi.fn(() => { throw new Error("denied"); }),
    })).not.toThrow();
  });
});
