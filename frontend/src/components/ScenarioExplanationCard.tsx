import type { ScenarioExplanation } from "../api/heatmap";

export type ScenarioExplanationState =
  | { status: "closed" }
  | { status: "loading"; cellId: string }
  | { status: "loaded"; explanation: ScenarioExplanation }
  | { status: "error"; cellId: string };

export function ScenarioExplanationCard({
  state,
  onClose,
}: {
  state: ScenarioExplanationState;
  onClose: () => void;
}) {
  if (state.status === "closed") return null;
  return (
    <aside className="scenario-explanation-card" aria-label="Почему здесь такой балл">
      <header>
        <div>
          <span>Аналитическая ячейка</span>
          <strong>Почему здесь такой балл?</strong>
        </div>
        <button type="button" onClick={onClose} aria-label="Закрыть объяснение">×</button>
      </header>
      {state.status === "loading" && <p role="status">Загружаем объяснение…</p>}
      {state.status === "error" && <p role="alert">Не удалось объяснить выбранную ячейку</p>}
      {state.status === "loaded" && (
        <>
          <div className="scenario-explanation-card__score">
            <span>Общий балл</span>
            <strong>{state.explanation.score.toFixed(1)}</strong>
          </div>
          <ul>
            {state.explanation.factors.map((factor) => (
              <li key={factor.metric_key}>
                <div>
                  <strong>{factor.label}</strong>
                  <span>Вес {factor.weight.toFixed(0)} · балл {factor.individual_score.toFixed(1)} · вклад {factor.contribution.toFixed(1)}</span>
                </div>
                {factor.target && (
                  <small>
                    {factor.target.name ?? "Без названия"} · {Math.round(factor.target.distance_m)} м
                    {factor.target.area_m2 === null
                      ? ""
                      : ` · ${(factor.target.area_m2 / 10_000).toFixed(1)} га`}
                  </small>
                )}
              </li>
            ))}
          </ul>
          <small>Значения соответствуют immutable score runs активной тепловой карты.</small>
        </>
      )}
    </aside>
  );
}
