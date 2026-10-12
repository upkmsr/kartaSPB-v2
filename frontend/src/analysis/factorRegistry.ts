export type FactorConfig = {
  id: string;
  label: string;
  category: string;
  metricKey: string;
  layerId: string;
  color: string;
  order: number;
};

export const factorRegistry: readonly FactorConfig[] = [
  { id: "kindergarten", label: "Детские сады", category: "education.kindergarten", metricKey: "education.kindergarten.accessibility_index", layerId: "kindergarten", color: "#ff9f43", order: 10 },
  { id: "school", label: "Школы", category: "education.school", metricKey: "education.school.accessibility_index", layerId: "school", color: "#ffd93d", order: 20 },
  { id: "public_transport", label: "Остановки транспорта", category: "transport.stop", metricKey: "transport.stop.accessibility_index", layerId: "stop", color: "#4dabf7", order: 30 },
  { id: "clinic", label: "Поликлиники", category: "healthcare.clinic", metricKey: "healthcare.clinic.accessibility_index", layerId: "clinic", color: "#4dd4c6", order: 40 },
  { id: "hospital", label: "Больницы", category: "healthcare.hospital", metricKey: "healthcare.hospital.accessibility_index", layerId: "hospital", color: "#ff6b6b", order: 50 },
  { id: "pharmacy", label: "Аптеки", category: "healthcare.pharmacy", metricKey: "healthcare.pharmacy.accessibility_index", layerId: "pharmacy", color: "#f783c4", order: 60 },
  { id: "park", label: "Парки", category: "nature.park", metricKey: "nature.park.accessibility_index", layerId: "park", color: "#69db7c", order: 70 },
  { id: "water", label: "Вода", category: "nature.water", metricKey: "nature.water.accessibility_index", layerId: "water", color: "#66d9e8", order: 80 },
] as const;

export const factorById = new Map(factorRegistry.map((factor) => [factor.id, factor]));
export const factorByMetric = new Map(
  factorRegistry.map((factor) => [factor.metricKey, factor]),
);
