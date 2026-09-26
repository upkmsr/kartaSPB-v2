import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SearchResult } from "../api/search";
import { SearchSection } from "./SearchSection";

const results: SearchResult[] = [
  {
    id: "c49e54e1-3481-4b07-9f81-0b161b57b62b",
    name: "Аптека № 1",
    categories: ["healthcare.pharmacy"],
    object_kind: "feature",
    geometry_type: "Point",
    representative_point: { type: "Point", coordinates: [30.3, 59.9] },
    bbox: [30.3, 59.9, 30.3, 59.9],
  },
  {
    id: "0014437e-092b-479f-a006-10c926604682",
    name: "Аптекарский сад с очень длинным названием",
    categories: ["nature.park", "education.school", "transport.stop"],
    object_kind: "feature",
    geometry_type: "Polygon",
    representative_point: { type: "Point", coordinates: [30.31, 59.91] },
    bbox: [30.3, 59.9, 30.32, 59.92],
  },
];

const response = (items: SearchResult[]) =>
  new Response(JSON.stringify({ type: "SearchResults", results: items }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

const renderSearch = (
  props: Partial<React.ComponentProps<typeof SearchSection>> = {},
) =>
  render(
    <SearchSection
      districtIds={[]}
      categoryKeys={["healthcare.pharmacy", "nature.park"]}
      selectedObjectId={null}
      onResultActivate={vi.fn()}
      {...props}
    />,
  );

describe("SearchSection", () => {
  beforeEach(() => vi.useFakeTimers());

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("waits for three normalized characters and the 250 ms debounce", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(results));
    renderSearch();
    const input = screen.getByRole("textbox", { name: "Поиск объектов" });
    expect(input).toHaveAttribute("maxlength", "100");

    fireEvent.change(input, { target: { value: "н" } });
    await act(async () => vi.advanceTimersByTimeAsync(300));
    fireEvent.change(input, { target: { value: "не" } });
    await act(async () => vi.advanceTimersByTimeAsync(300));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByText("Введите минимум 3 символа")).toBeInTheDocument();

    fireEvent.change(input, { target: { value: "нев" } });
    expect(screen.getByText("Ищем объекты…")).toBeInTheDocument();
    await act(async () => vi.advanceTimersByTimeAsync(249));
    expect(fetchMock).not.toHaveBeenCalled();
    await act(async () => vi.advanceTimersByTimeAsync(1));
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(screen.getByText("Аптека № 1")).toBeInTheDocument();
  });

  it("debounces rapid typing to one final normalized request", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(results));
    renderSearch();
    const input = screen.getByRole("textbox", { name: "Поиск объектов" });

    for (const value of ["нев", "невс", "невск", "невский"]) {
      fireEvent.change(input, { target: { value } });
      await act(async () => vi.advanceTimersByTimeAsync(50));
    }
    await act(async () => vi.advanceTimersByTimeAsync(250));

    expect(fetchMock).toHaveBeenCalledOnce();
    const url = new URL(String(fetchMock.mock.calls[0][0]), "http://localhost");
    expect(url.searchParams.get("q")).toBe("невский");
  });

  it("clear aborts the active request without closing the selected object", async () => {
    let signal: AbortSignal | undefined;
    vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
      signal = init?.signal as AbortSignal;
      return new Promise<Response>(() => undefined);
    });
    renderSearch({ selectedObjectId: results[0].id });
    const input = screen.getByRole("textbox", { name: "Поиск объектов" });
    fireEvent.change(input, { target: { value: "аптека" } });
    await act(async () => vi.advanceTimersByTimeAsync(250));
    expect(signal?.aborted).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Очистить поиск" }));
    expect(signal?.aborted).toBe(true);
    expect(input).toHaveValue("");
    expect(screen.queryByText("Ищем объекты…")).not.toBeInTheDocument();
  });

  it("renders human labels, selected state, and supports Arrow keys, Enter, and Escape", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(response(results));
    const onResultActivate = vi.fn();
    renderSearch({ selectedObjectId: results[1].id, onResultActivate });
    const input = screen.getByRole("textbox", { name: "Поиск объектов" });
    fireEvent.change(input, { target: { value: "аптека" } });
    await act(async () => vi.advanceTimersByTimeAsync(250));

    expect(screen.getByText("Аптеки")).toBeInTheDocument();
    expect(screen.getByText("Парки · Школы +1")).toBeInTheDocument();
    const second = screen.getByRole("button", {
      name: /Аптекарский сад с очень длинным названием.*Выбран/,
    });
    expect(second).toHaveAttribute("aria-current", "true");

    input.focus();
    fireEvent.keyDown(input, { key: "ArrowDown" });
    const first = screen.getByRole("button", { name: /Аптека № 1.*Аптеки/ });
    expect(first).toHaveFocus();
    fireEvent.keyDown(first, { key: "ArrowDown" });
    expect(second).toHaveFocus();
    fireEvent.keyDown(second, { key: "ArrowUp" });
    expect(first).toHaveFocus();
    fireEvent.keyDown(first, { key: "Enter" });
    expect(onResultActivate).toHaveBeenCalledWith(results[0]);
    fireEvent.keyDown(first, { key: "Escape" });
    expect(input).toHaveFocus();
    expect(screen.queryByRole("list", { name: "Результаты поиска" })).not.toBeInTheDocument();
  });

  it("reruns an active query for district and category scope changes", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(results));
    const { rerender } = renderSearch();
    const input = screen.getByRole("textbox", { name: "Поиск объектов" });
    fireEvent.change(input, { target: { value: "школа" } });
    await act(async () => vi.advanceTimersByTimeAsync(250));

    rerender(
      <SearchSection
        districtIds={["central", "admiralteysky"]}
        categoryKeys={["education.school"]}
        selectedObjectId={null}
        onResultActivate={vi.fn()}
      />,
    );
    await act(async () => vi.advanceTimersByTimeAsync(250));

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const scoped = new URL(String(fetchMock.mock.calls[1][0]), "http://localhost");
    expect(scoped.searchParams.get("districts")).toBe("central,admiralteysky");
    expect(scoped.searchParams.get("categories")).toBe("education.school");

    rerender(
      <SearchSection
        districtIds={[]}
        categoryKeys={[]}
        selectedObjectId={null}
        onResultActivate={vi.fn()}
      />,
    );
    expect(screen.getByText("Включите хотя бы один слой")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("distinguishes empty and retryable error states", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(response([]))
      .mockRejectedValueOnce(new Error("network unavailable"))
      .mockResolvedValueOnce(response(results));
    renderSearch();
    const input = screen.getByRole("textbox", { name: "Поиск объектов" });

    fireEvent.change(input, { target: { value: "пусто" } });
    await act(async () => vi.advanceTimersByTimeAsync(250));
    expect(screen.getByText("Ничего не найдено")).toBeInTheDocument();

    fireEvent.change(input, { target: { value: "ошибка" } });
    await act(async () => vi.advanceTimersByTimeAsync(250));
    expect(screen.getByRole("alert")).toHaveTextContent("Не удалось выполнить поиск");
    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));
    await act(async () => vi.advanceTimersByTimeAsync(250));
    expect(screen.getByText("Аптека № 1")).toBeInTheDocument();
  });
});
