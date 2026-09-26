import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import {
  LatestSearchRequest,
  MAX_SEARCH_QUERY_LENGTH,
  MIN_SEARCH_QUERY_LENGTH,
  SEARCH_DEBOUNCE_MS,
  normalizeSearchQuery,
  type SearchResult,
} from "../api/search";
import { categoryLabel } from "../map/layerRegistry";

type SearchState =
  | { status: "idle" }
  | { status: "below-minimum" }
  | { status: "loading" }
  | { status: "no-categories" }
  | { status: "results"; results: SearchResult[] }
  | { status: "empty" }
  | { status: "error" };

export type SearchSectionProps = {
  districtIds: readonly string[];
  categoryKeys: readonly string[];
  selectedObjectId: string | null;
  onResultActivate: (result: SearchResult) => void;
};

export function SearchSection({
  districtIds,
  categoryKeys,
  selectedObjectId,
  onResultActivate,
}: SearchSectionProps) {
  const [query, setQuery] = useState("");
  const [state, setState] = useState<SearchState>({ status: "idle" });
  const [retry, setRetry] = useState(0);
  const [listOpen, setListOpen] = useState(true);
  const [activeIndex, setActiveIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const resultRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const requestRef = useRef(new LatestSearchRequest());
  const normalizedQuery = normalizeSearchQuery(query);

  useEffect(() => {
    const request = requestRef.current;
    if (normalizedQuery.length === 0) {
      request.cancel();
      setState({ status: "idle" });
      setActiveIndex(-1);
      return;
    }
    if (normalizedQuery.length < MIN_SEARCH_QUERY_LENGTH) {
      request.cancel();
      setState({ status: "below-minimum" });
      setActiveIndex(-1);
      return;
    }
    if (categoryKeys.length === 0) {
      request.cancel();
      setState({ status: "no-categories" });
      setActiveIndex(-1);
      return;
    }

    setState({ status: "loading" });
    setListOpen(true);
    setActiveIndex(-1);
    const timer = window.setTimeout(() => {
      void request.run(
        {
          query: normalizedQuery,
          categoryKeys,
          districtIds,
          limit: 20,
        },
        (results) => {
          setState(results.length > 0 ? { status: "results", results } : { status: "empty" });
        },
        () => setState({ status: "error" }),
      );
    }, SEARCH_DEBOUNCE_MS);

    return () => {
      window.clearTimeout(timer);
      request.cancel();
    };
  }, [normalizedQuery, categoryKeys, districtIds, retry]);

  const results = state.status === "results" ? state.results : [];

  const clearSearch = () => {
    requestRef.current.cancel();
    setQuery("");
    setListOpen(true);
    setActiveIndex(-1);
    inputRef.current?.focus();
  };

  const focusResult = (index: number) => {
    if (results.length === 0) return;
    const nextIndex = Math.max(0, Math.min(index, results.length - 1));
    setActiveIndex(nextIndex);
    resultRefs.current[nextIndex]?.focus();
  };

  const closeResults = () => {
    setListOpen(false);
    setActiveIndex(-1);
    inputRef.current?.focus();
  };

  const handleInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" && results.length > 0 && listOpen) {
      event.preventDefault();
      focusResult(0);
    } else if (event.key === "Escape" && listOpen) {
      event.preventDefault();
      closeResults();
    }
  };

  const handleResultKeyDown = (
    event: KeyboardEvent<HTMLButtonElement>,
    index: number,
    result: SearchResult,
  ) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      focusResult(index + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (index === 0) {
        setActiveIndex(-1);
        inputRef.current?.focus();
      } else {
        focusResult(index - 1);
      }
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeResults();
    } else if (event.key === "Enter") {
      event.preventDefault();
      onResultActivate(result);
    }
  };

  return (
    <section className="search-control" aria-labelledby="search-heading">
      <p className="section-label" id="search-heading">
        Поиск
      </p>
      <div className="search-control__field">
        <label className="visually-hidden" htmlFor="catalog-search">
          Поиск объектов
        </label>
        <span className="search-control__icon" aria-hidden="true">
          ⌕
        </span>
        <input
          ref={inputRef}
          id="catalog-search"
          type="text"
          value={query}
          maxLength={MAX_SEARCH_QUERY_LENGTH}
          placeholder="Поиск объектов"
          autoComplete="off"
          aria-controls="catalog-search-results"
          onChange={(event) => {
            setQuery(event.target.value);
            setListOpen(true);
          }}
          onKeyDown={handleInputKeyDown}
        />
        {query.length > 0 && (
          <button
            className="search-control__clear"
            type="button"
            onClick={clearSearch}
            aria-label="Очистить поиск"
          >
            ×
          </button>
        )}
      </div>

      {listOpen && state.status === "below-minimum" && (
        <p className="search-control__hint">Введите минимум 3 символа</p>
      )}
      {listOpen && state.status === "loading" && (
        <div className="search-control__state" role="status">
          <span className="loading-dot" /> Ищем объекты…
        </div>
      )}
      {listOpen && state.status === "no-categories" && (
        <div className="search-control__state" role="status">
          Включите хотя бы один слой
        </div>
      )}
      {listOpen && state.status === "empty" && (
        <div className="search-control__state" role="status">
          Ничего не найдено
        </div>
      )}
      {listOpen && state.status === "error" && (
        <div className="search-control__state search-control__state--error" role="alert">
          <span>Не удалось выполнить поиск.</span>
          <button className="text-button" type="button" onClick={() => setRetry((value) => value + 1)}>
            Повторить
          </button>
        </div>
      )}
      {listOpen && state.status === "results" && (
        <ul className="search-results" id="catalog-search-results" aria-label="Результаты поиска">
          {state.results.map((result, index) => {
            const selected = selectedObjectId === result.id;
            const labels = result.categories.slice(0, 2).map(categoryLabel);
            const remaining = result.categories.length - labels.length;
            return (
              <li key={result.id}>
                <button
                  ref={(element) => {
                    resultRefs.current[index] = element;
                  }}
                  className={selected ? "search-result search-result--selected" : "search-result"}
                  type="button"
                  aria-current={selected ? "true" : undefined}
                  onFocus={() => setActiveIndex(index)}
                  onKeyDown={(event) => handleResultKeyDown(event, index, result)}
                  onClick={() => onResultActivate(result)}
                >
                  <span className="search-result__name">{result.name}</span>
                  <span className="search-result__meta">
                    {labels.join(" · ")}
                    {remaining > 0 ? ` +${remaining}` : ""}
                  </span>
                  {selected && <span className="visually-hidden">Выбран</span>}
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {activeIndex >= 0 && <span className="visually-hidden">Результат {activeIndex + 1}</span>}
    </section>
  );
}
