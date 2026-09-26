import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { District } from "./api/districts";
import { App } from "./App";

vi.mock("./map/MapView", () => ({
  MapView: ({
    districtIds,
    navigationRequest,
    selectedFeatureId,
  }: {
    districtIds: readonly string[];
    navigationRequest:
      | { kind: "bbox"; bbox: [number, number, number, number] }
      | { kind: "point"; center: [number, number]; zoom: number }
      | null;
    selectedFeatureId: string | null;
  }) => (
    <div aria-label="Карта Санкт-Петербурга">
      <span data-testid="map-districts">{districtIds.join(",")}</span>
      <span data-testid="map-navigation">
        {navigationRequest?.kind === "bbox"
          ? navigationRequest.bbox.join(",")
          : navigationRequest?.kind === "point"
            ? navigationRequest.center.join(",")
            : ""}
      </span>
      <span data-testid="map-selected">{selectedFeatureId ?? ""}</span>
    </div>
  ),
}));

const readiness = {
  status: "ready",
  database: { status: "ready", detail: null },
  postgis: { status: "ready", detail: "3.5.0" },
  migrations: { status: "ready", detail: "20260925_0007" },
};

const districts: District[] = Array.from({ length: 18 }, (_, index) => ({
  id: `00000000-0000-0000-0000-${String(index + 1).padStart(12, "0")}`,
  name: index === 0 ? "Центральный" : index === 1 ? "Приморский" : `Район ${index + 1}`,
  slug: `district-${index + 1}`,
  display_order: index + 1,
  bbox: [
    Number((30 + index / 100).toFixed(2)),
    59,
    Number((30.1 + index / 100).toFixed(2)),
    59.1,
  ],
}));

const response = (payload: unknown) =>
  new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

const mockHealthyApi = () =>
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.includes("/api/health/ready")) return Promise.resolve(response(readiness));
    if (url.includes("/api/districts")) return Promise.resolve(response({ districts }));
    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });

describe("App", () => {
  afterEach(() => vi.restoreAllMocks());

  it("renders the shell, 18 ordered districts, layers, and panel collapse", async () => {
    mockHealthyApi();
    render(<App />);

    expect(screen.getByRole("heading", { name: "KARTASPB" })).toBeInTheDocument();
    expect(screen.getByLabelText("Панель управления картой")).toBeInTheDocument();
    expect(screen.getByLabelText("Рабочая область карты")).toBeInTheDocument();
    expect(screen.getByLabelText("Карта Санкт-Петербурга")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Дороги/ })).toBeChecked();

    await waitFor(() => expect(screen.getAllByText("READY")).toHaveLength(2));
    await screen.findByRole("checkbox", { name: "Центральный" });
    expect(document.querySelectorAll('input[type="checkbox"]')).toHaveLength(28);
    const scrollArea = screen.getByRole("region", {
      name: "Прокручиваемые настройки карты",
    });
    expect(scrollArea).toHaveClass("sidebar__content");
    expect(within(scrollArea).getByRole("checkbox", { name: "Район 18" })).toBeInTheDocument();
    expect(within(scrollArea).getByRole("checkbox", { name: /Дороги/ })).toBeInTheDocument();
    const districtList = screen.getByText("Центральный").closest(".district-control__list");
    expect(districtList).not.toBeNull();
    expect(within(districtList as HTMLElement).getAllByRole("checkbox")[0]).toHaveAccessibleName(
      "Центральный",
    );

    fireEvent.click(screen.getByRole("button", { name: "Свернуть панель" }));
    expect(screen.queryByRole("checkbox", { name: "Центральный" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Развернуть панель" }));
    expect(screen.getByRole("checkbox", { name: "Центральный" })).toBeInTheDocument();
  }, 10_000);

  it("uses district UUIDs for one, many, unselect, and clear selection", async () => {
    mockHealthyApi();
    render(<App />);
    await screen.findByRole("checkbox", { name: "Центральный" });

    fireEvent.click(
      screen.getByRole("button", { name: "Показать Центральный район на карте" }),
    );
    expect(screen.getByTestId("map-navigation")).toHaveTextContent("30,59,30.1,59.1");

    fireEvent.click(screen.getByRole("checkbox", { name: "Центральный" }));
    expect(screen.getByText("1 выбрано")).toBeInTheDocument();
    expect(screen.getByTestId("map-districts")).toHaveTextContent(districts[0].id);

    fireEvent.click(screen.getByRole("checkbox", { name: "Приморский" }));
    expect(screen.getByText("2 выбрано")).toBeInTheDocument();
    expect(screen.getByTestId("map-districts")).toHaveTextContent(
      `${districts[0].id},${districts[1].id}`,
    );
    fireEvent.click(screen.getByRole("button", { name: "Показать выбранные" }));
    expect(screen.getByTestId("map-navigation")).toHaveTextContent("30,59,30.11,59.1");

    fireEvent.click(screen.getByRole("checkbox", { name: "Центральный" }));
    expect(screen.getByText("1 выбрано")).toBeInTheDocument();
    expect(screen.getByTestId("map-districts")).not.toHaveTextContent(districts[0].id);

    fireEvent.click(screen.getByRole("button", { name: "Все районы" }));
    expect(screen.getByText("Без ограничений")).toBeInTheDocument();
    expect(screen.getByTestId("map-districts")).toBeEmptyDOMElement();
  });

  it("keeps the map available and retries a failed district request", async () => {
    let districtCalls = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/health/ready")) return Promise.resolve(response(readiness));
      if (url.includes("/api/districts")) {
        districtCalls += 1;
        return districtCalls === 1
          ? Promise.reject(new Error("district service unavailable"))
          : Promise.resolve(response({ districts }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });

    render(<App />);
    expect(screen.getByLabelText("Карта Санкт-Петербурга")).toBeInTheDocument();
    expect(await screen.findByText("Не удалось загрузить районы.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));
    expect(await screen.findByRole("checkbox", { name: "Центральный" })).toBeInTheDocument();
    expect(districtCalls).toBe(2);
  });

  it("shows offline state when the backend cannot be reached", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network unavailable"));
    render(<App />);
    await waitFor(() => expect(screen.getAllByText("OFFLINE")).toHaveLength(2));
    expect(screen.getByText("Не удалось загрузить районы.")).toBeInTheDocument();
  });

  it("opens the existing ObjectCard and navigates from a canonical search result", async () => {
    const resultId = "c49e54e1-3481-4b07-9f81-0b161b57b62b";
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/health/ready")) return Promise.resolve(response(readiness));
      if (url.includes("/api/districts")) return Promise.resolve(response({ districts }));
      if (url.includes("/api/search")) {
        return Promise.resolve(
          response({
            type: "SearchResults",
            results: [
              {
                id: resultId,
                name: "Аптека у Невы",
                categories: ["healthcare.pharmacy"],
                object_kind: "feature",
                geometry_type: "Point",
                representative_point: { type: "Point", coordinates: [30.3, 59.9] },
                bbox: [30.3, 59.9, 30.3, 59.9],
              },
            ],
          }),
        );
      }
      if (url.includes(`/api/objects/${resultId}`)) {
        return Promise.resolve(
          response({
            id: resultId,
            name: "Аптека у Невы",
            categories: ["healthcare.pharmacy"],
            object_kind: "feature",
            geometry_type: "Point",
            properties: {},
            sources: [],
          }),
        );
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    render(<App />);
    const input = screen.getByRole("textbox", { name: "Поиск объектов" });
    fireEvent.change(input, { target: { value: "аптека" } });
    const result = await screen.findByRole("button", { name: /Аптека у Невы.*Аптеки/ });

    const searchUrl = new URL(
      String(
        vi.mocked(globalThis.fetch).mock.calls.find(([request]) =>
          String(request).includes("/api/search"),
        )?.[0],
      ),
      "http://localhost",
    );
    expect(searchUrl.searchParams.get("categories")).toContain("healthcare.pharmacy");
    fireEvent.click(result);

    expect(screen.getByTestId("map-selected")).toHaveTextContent(resultId);
    expect(screen.getByTestId("map-navigation")).toHaveTextContent("30.3,59.9");
    expect(await screen.findByRole("heading", { name: "Аптека у Невы" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Очистить поиск" }));
    expect(screen.getByRole("heading", { name: "Аптека у Невы" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Закрыть карточку" }));
    expect(screen.queryByLabelText("Карточка объекта")).not.toBeInTheDocument();
  });
});
