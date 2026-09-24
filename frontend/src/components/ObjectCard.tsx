import { categoryLabel } from "../map/layerRegistry";
import type { ObjectCardState } from "../map/mapTypes";

export type ObjectCardProps = {
  state: ObjectCardState;
  onClose: () => void;
};

const propertyValue = (value: unknown): string | null => {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return null;
};

export function ObjectCard({ state, onClose }: ObjectCardProps) {
  if (state.status === "closed") return null;

  return (
    <aside className="object-card" aria-label="Карточка объекта">
      <button className="object-card__close" type="button" onClick={onClose} aria-label="Закрыть карточку">
        ×
      </button>

      {state.status === "loading" && (
        <div className="object-card__state" role="status">
          <span className="loading-dot" />
          Загружаем объект
        </div>
      )}

      {state.status === "not-found" && (
        <div className="object-card__state">
          <p className="eyebrow">Объект недоступен</p>
          <h2>Данные больше не опубликованы</h2>
        </div>
      )}

      {state.status === "error" && (
        <div className="object-card__state">
          <p className="eyebrow eyebrow--error">Ошибка связи</p>
          <h2>Не удалось открыть карточку</h2>
          <p>Выберите объект ещё раз после восстановления соединения.</p>
        </div>
      )}

      {state.status === "loaded" && (
        <div className="object-card__content">
          <p className="eyebrow">Canonical object</p>
          <h2>{state.detail.name ?? "Без названия"}</h2>
          <div className="object-card__categories">
            {state.detail.categories.map((category) => (
              <span key={category}>{categoryLabel(category)}</span>
            ))}
          </div>

          <dl className="object-card__facts">
            <div>
              <dt>Геометрия</dt>
              <dd>{state.detail.geometry_type}</dd>
            </div>
            <div>
              <dt>Тип</dt>
              <dd>{state.detail.object_kind}</dd>
            </div>
            {Object.entries(state.detail.properties)
              .map(([key, value]) => [key, propertyValue(value)] as const)
              .filter((entry): entry is readonly [string, string] => entry[1] !== null)
              .slice(0, 5)
              .map(([key, value]) => (
                <div key={key}>
                  <dt>{key}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
          </dl>

          {state.detail.sources.length > 0 && (
            <section className="object-card__sources">
              <p className="section-label">Источники</p>
              {state.detail.sources.map((source) => (
                <div className="source-summary" key={`${source.provider}:${source.object_type}:${source.object_id}`}>
                  <strong>{source.provider}</strong>
                  <span>
                    {source.object_type} {source.object_id}
                  </span>
                  <small>
                    {source.source_version ?? "версия не указана"} · {source.geometry_quality}
                  </small>
                </div>
              ))}
            </section>
          )}
        </div>
      )}
    </aside>
  );
}
