import { factorByMetric } from "../analysis/factorRegistry";

export type InfluenceInspection = {
  cellId: string;
  scores: Array<{
    metricKey: string;
    score: number;
    minimumScore: number;
    scoreRunId: string;
  }>;
};

export function InfluenceInspectorCard({
  inspection,
  onClose,
}: {
  inspection: InfluenceInspection | null;
  onClose: () => void;
}) {
  if (inspection === null) return null;
  return (
    <aside className="influence-inspector" aria-label="Состав влияния">
      <header>
        <div>
          <span>Ячейка анализа</span>
          <strong>{inspection.cellId}</strong>
        </div>
        <button type="button" aria-label="Закрыть состав влияния" onClick={onClose}>×</button>
      </header>
      <ul>
        {inspection.scores.map((item) => {
          const factor = factorByMetric.get(item.metricKey);
          const visible = item.score >= item.minimumScore;
          return (
            <li key={item.metricKey}>
              <span className="influence-factor__swatch" style={{ background: factor?.color }} aria-hidden="true" />
              <div>
                <strong>{factor?.label ?? item.metricKey}</strong>
                <small>порог {item.minimumScore} · {visible ? "видим" : "скрыт"}</small>
                <small>immutable run {item.scoreRunId.slice(0, 8)}…</small>
              </div>
              <output>{item.score.toFixed(1)}</output>
            </li>
          );
        })}
      </ul>
      <p>Связанный исходный объект показывается только через обычный объектный слой: tile не утверждает недостоверную связь.</p>
    </aside>
  );
}
