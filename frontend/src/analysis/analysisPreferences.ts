export const ANALYSIS_PREFERENCES_VERSION = 1 as const;
export const ANALYSIS_PREFERENCES_STORAGE_KEY = "kartaspb.analysis-preferences";

export type AnalysisMode = "independent" | "composite";

export type IndependentLayerState = {
  enabled: boolean;
  minimumScore: number;
  showObjects: boolean;
};

export type AnalysisPreferences = {
  version: typeof ANALYSIS_PREFERENCES_VERSION;
  activeAnalysisMode: AnalysisMode;
  influenceLayers: Record<string, IndependentLayerState>;
  scenarioWeights: Record<string, number>;
  scenarioMinScore: number;
};

type StorageLike = Pick<Storage, "getItem" | "setItem">;

const availableStorage = (): StorageLike | null => {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
};

export const defaultAnalysisPreferences = (): AnalysisPreferences => ({
  version: ANALYSIS_PREFERENCES_VERSION,
  activeAnalysisMode: "independent",
  influenceLayers: {},
  scenarioWeights: {},
  scenarioMinScore: 40,
});

const isScore = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 100;

export const loadAnalysisPreferences = (
  storage: StorageLike | null = availableStorage(),
): AnalysisPreferences => {
  const defaults = defaultAnalysisPreferences();
  if (storage === null) return defaults;
  try {
    const raw = storage.getItem(ANALYSIS_PREFERENCES_STORAGE_KEY);
    if (raw === null) return defaults;
    const value = JSON.parse(raw) as Partial<AnalysisPreferences>;
    if (value.version !== ANALYSIS_PREFERENCES_VERSION) return defaults;
    if (value.activeAnalysisMode !== "independent" && value.activeAnalysisMode !== "composite") {
      return defaults;
    }
    const scenarioWeights = Object.fromEntries(
      Object.entries(value.scenarioWeights ?? {}).filter(
        ([key, weight]) => key.length > 0 && isScore(weight),
      ),
    );
    const influenceLayers = Object.fromEntries(
      Object.entries(value.influenceLayers ?? {}).filter(
        ([key, state]) =>
          key.length > 0 &&
          typeof state === "object" &&
          state !== null &&
          typeof state.enabled === "boolean" &&
          isScore(state.minimumScore) &&
          state.minimumScore <= 99 &&
          typeof state.showObjects === "boolean",
      ),
    );
    return {
      version: ANALYSIS_PREFERENCES_VERSION,
      activeAnalysisMode: value.activeAnalysisMode,
      influenceLayers,
      scenarioWeights,
      scenarioMinScore:
        isScore(value.scenarioMinScore) && value.scenarioMinScore <= 99
          ? value.scenarioMinScore
          : defaults.scenarioMinScore,
    };
  } catch {
    return defaults;
  }
};

export const saveAnalysisPreferences = (
  preferences: AnalysisPreferences,
  storage: StorageLike | null = availableStorage(),
): void => {
  if (storage === null) return;
  try {
    storage.setItem(ANALYSIS_PREFERENCES_STORAGE_KEY, JSON.stringify(preferences));
  } catch {
    // Local preferences are optional when storage is unavailable.
  }
};
