import { useState } from "react";
import type { District } from "../api/districts";

export type DistrictLoadState =
  | { status: "loading" }
  | { status: "loaded"; districts: District[] }
  | { status: "error" };

export type DistrictSectionProps = {
  state: DistrictLoadState;
  selectedDistrictIds: ReadonlySet<string>;
  onToggle: (districtId: string) => void;
  onClear: () => void;
  onLocate: (district: District) => void;
  onLocateSelected: () => void;
  onRetry: () => void;
};

export function DistrictSection({
  state,
  selectedDistrictIds,
  onToggle,
  onClear,
  onLocate,
  onLocateSelected,
  onRetry,
}: DistrictSectionProps) {
  const selectedCount = selectedDistrictIds.size;
  const [expanded, setExpanded] = useState(true);

  return (
    <section className="district-control" aria-labelledby="districts-heading">
      <div className="district-control__heading">
        <button
          className="district-control__toggle"
          type="button"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
          aria-controls="district-control-content"
        >
          <span>
            <span className="section-label" id="districts-heading">
              Районы
            </span>
            <span className="district-control__count">
              {selectedCount === 0 ? "Без ограничений" : `${selectedCount} выбрано`}
            </span>
          </span>
          <span className="district-control__chevron" aria-hidden="true">
            {expanded ? "⌃" : "⌄"}
          </span>
        </button>
        <button
          className="text-button"
          type="button"
          onClick={onClear}
          disabled={selectedCount === 0}
        >
          Все районы
        </button>
      </div>

      {expanded && (
        <div id="district-control-content">
          {state.status === "loading" && (
            <div className="district-control__state" role="status">
              <span className="loading-dot" /> Загружаем районы…
            </div>
          )}

          {state.status === "error" && (
            <div className="district-control__state district-control__state--error" role="alert">
              <span>Не удалось загрузить районы.</span>
              <button className="text-button" type="button" onClick={onRetry}>
                Повторить
              </button>
            </div>
          )}

          {state.status === "loaded" && state.districts.length === 0 && (
            <div className="district-control__state" role="status">
              Районы пока недоступны.
            </div>
          )}

          {state.status === "loaded" && state.districts.length > 0 && (
            <>
              <div className="district-control__list">
                {state.districts.map((district) => {
                  const selected = selectedDistrictIds.has(district.id);
                  const inputId = `district-${district.id}`;
                  return (
                    <div
                      className={
                        selected ? "district-row district-row--selected" : "district-row"
                      }
                      key={district.id}
                    >
                      <input
                        id={inputId}
                        type="checkbox"
                        checked={selected}
                        onChange={() => onToggle(district.id)}
                      />
                      <label htmlFor={inputId}>{district.name}</label>
                      <button
                        className="district-row__locate"
                        type="button"
                        onClick={() => onLocate(district)}
                        aria-label={`Показать ${district.name} район на карте`}
                        title="Показать район на карте"
                      >
                        ⌖
                      </button>
                    </div>
                  );
                })}
              </div>
              <button
                className="district-control__fit"
                type="button"
                onClick={onLocateSelected}
                disabled={selectedCount === 0}
              >
                Показать выбранные
              </button>
            </>
          )}
        </div>
      )}
    </section>
  );
}
