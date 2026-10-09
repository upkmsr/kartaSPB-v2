import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { PreparedHeatmap, ScenarioDimension } from "../api/heatmap";
import { ScenarioBuilder } from "./ScenarioBuilder";

const dimensions: ScenarioDimension[] = [
  ["kindergarten", "Детские сады", "education", "Образование"],
  ["school", "Школы", "education", "Образование"],
  ["public_transport", "Общественный транспорт", "transport", "Транспорт"],
  ["clinic", "Поликлиники", "healthcare", "Медицина"],
  ["hospital", "Больницы", "healthcare", "Медицина"],
  ["pharmacy", "Аптеки", "healthcare", "Медицина"],
  ["park", "Парки", "nature", "Природа"],
  ["water", "Вода / набережные", "nature", "Природа"],
].map(([key, label, group, group_label], index) => ({
  key,
  label,
  group,
  group_label,
  metric_key: `test.${key}.accessibility_index`,
  display_order: (index + 1) * 10,
}));

const prepared = (grid = "spb-square-200m-v1"): PreparedHeatmap => ({
  grid_version: grid,
  weights: Object.fromEntries(dimensions.map((item) => [item.metric_key, 50])),
  scoring_signature: "a".repeat(64),
  spec: "opaque",
  cell_count: grid.includes("50m") ? 580597 : 36292,
  min: 0,
  max: 100,
  mean: 50,
  tile_url_template: "/api/analysis/heatmap/tiles/signature/{z}/{x}/{y}.mvt?spec=opaque",
  delivery_version: "heatmap-mvt-v1",
});

const jsonResponse = (payload: unknown) =>
  new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

const props = {
  active: false,
  activeHeatmap: null,
  districtIds: [] as string[],
  zoom: 12,
  displayRange: { min: 40, max: 100 },
  tileError: null,
  onPrepared: vi.fn(),
  onDisplayRangeChange: vi.fn(),
  onHide: vi.fn(),
};

afterEach(() => vi.restoreAllMocks());

it("renders exactly eight explicit zero-weight sliders and quick actions", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(dimensions));
  const onHide = vi.fn();
  render(<ScenarioBuilder {...props} onHide={onHide} />);
  const sliders = await screen.findAllByRole("slider");
  expect(sliders).toHaveLength(8);
  expect(sliders.every((slider) => slider.getAttribute("value") === "0")).toBe(true);
  expect(screen.getByRole("button", { name: "Показать сценарий" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "По району" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Все поровну" }));
  expect(sliders.every((slider) => slider.getAttribute("value") === "50")).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Сбросить" }));
  expect(sliders.every((slider) => slider.getAttribute("value") === "0")).toBe(true);
  expect(onHide).toHaveBeenCalledOnce();
});

it("sends all visible priorities, then debounces rapid live changes", async () => {
  const onPrepared = vi.fn();
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.includes("/scenarios/dimensions")) return Promise.resolve(jsonResponse(dimensions));
    return Promise.resolve(jsonResponse(prepared()));
  });
  const { rerender } = render(<ScenarioBuilder {...props} onPrepared={onPrepared} />);
  await screen.findAllByRole("slider");
  fireEvent.click(screen.getByRole("button", { name: "Все поровну" }));
  fireEvent.click(screen.getByRole("button", { name: "Показать сценарий" }));
  await waitFor(() => expect(onPrepared).toHaveBeenCalledOnce());
  const firstPrepare = fetchMock.mock.calls.find(([input]) => String(input).includes("/heatmap/prepare"));
  const firstBody = JSON.parse(String((firstPrepare?.[1] as RequestInit).body));
  expect(Object.keys(firstBody.weights)).toHaveLength(8);
  expect(new Set(Object.values(firstBody.weights))).toEqual(new Set([50]));

  rerender(<ScenarioBuilder {...props} active activeHeatmap={prepared()} onPrepared={onPrepared} />);
  const school = screen.getByRole("slider", { name: "Школы" });
  fireEvent.change(school, { target: { value: "60" } });
  fireEvent.change(school, { target: { value: "61" } });
  fireEvent.change(school, { target: { value: "62" } });
  await waitFor(() => expect(onPrepared).toHaveBeenCalledTimes(2), { timeout: 1200 });
  const prepareCalls = fetchMock.mock.calls.filter(([input]) => String(input).includes("/heatmap/prepare"));
  expect(prepareCalls).toHaveLength(2);
  const secondBody = JSON.parse(String((prepareCalls[1][1] as RequestInit).body));
  expect(secondBody.weights[dimensions[1].metric_key]).toBe(62);
});

it("automatically switches an active Auto scenario from 200 m to 50 m at z13", async () => {
  const onPrepared = vi.fn();
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    if (String(input).includes("/scenarios/dimensions")) {
      return Promise.resolve(jsonResponse(dimensions));
    }
    const body = JSON.parse(String(init?.body));
    return Promise.resolve(jsonResponse(prepared(body.grid_version)));
  });
  const { rerender } = render(<ScenarioBuilder {...props} onPrepared={onPrepared} />);
  await screen.findAllByRole("slider");
  fireEvent.click(screen.getByRole("button", { name: "Все поровну" }));
  fireEvent.click(screen.getByRole("button", { name: "Показать сценарий" }));
  await waitFor(() => expect(onPrepared).toHaveBeenCalledOnce());
  expect(onPrepared.mock.calls[0][0].grid_version).toBe("spb-square-200m-v1");
  rerender(
    <ScenarioBuilder
      {...props}
      active
      activeHeatmap={prepared()}
      zoom={13}
      onPrepared={onPrepared}
    />,
  );
  await waitFor(() => expect(onPrepared).toHaveBeenCalledTimes(2), { timeout: 1200 });
  expect(onPrepared.mock.calls[1][0].grid_version).toBe("spb-square-50m-v1");
  rerender(
    <ScenarioBuilder
      {...props}
      active
      activeHeatmap={prepared("spb-square-50m-v1")}
      zoom={12}
      onPrepared={onPrepared}
    />,
  );
  await waitFor(() => expect(onPrepared).toHaveBeenCalledTimes(3), { timeout: 1200 });
  expect(onPrepared.mock.calls[2][0].grid_version).toBe("spb-square-200m-v1");
  expect(fetchMock.mock.calls.filter(([input]) => String(input).includes("/heatmap/prepare"))).toHaveLength(3);
});

it("omits zero weights and aborts a stale live prepare", async () => {
  const onPrepared = vi.fn();
  const prepareResolvers: Array<(response: Response) => void> = [];
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    if (String(input).includes("/scenarios/dimensions")) {
      return Promise.resolve(jsonResponse(dimensions));
    }
    return new Promise<Response>((resolve) => prepareResolvers.push(resolve));
  });
  const { rerender } = render(<ScenarioBuilder {...props} onPrepared={onPrepared} />);
  await screen.findAllByRole("slider");
  fireEvent.click(screen.getByRole("button", { name: "Все поровну" }));
  fireEvent.change(screen.getByRole("slider", { name: "Школы" }), {
    target: { value: "0" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Показать сценарий" }));
  await waitFor(() => expect(prepareResolvers).toHaveLength(1));
  const prepareCalls = () =>
    fetchMock.mock.calls.filter(([input]) => String(input).includes("/heatmap/prepare"));
  const firstBody = JSON.parse(String((prepareCalls()[0][1] as RequestInit).body));
  expect(Object.keys(firstBody.weights)).toHaveLength(7);
  expect(firstBody.weights[dimensions[1].metric_key]).toBeUndefined();

  rerender(
    <ScenarioBuilder
      {...props}
      active
      activeHeatmap={prepared()}
      onPrepared={onPrepared}
    />,
  );
  fireEvent.change(screen.getByRole("slider", { name: "Детские сады" }), {
    target: { value: "51" },
  });
  await waitFor(() => expect(prepareResolvers).toHaveLength(2), { timeout: 1200 });
  expect((prepareCalls()[0][1] as RequestInit).signal?.aborted).toBe(true);
  prepareResolvers[1](jsonResponse(prepared()));
  await waitFor(() => expect(onPrepared).toHaveBeenCalledOnce());
  prepareResolvers[0](jsonResponse(prepared()));
  await new Promise((resolve) => window.setTimeout(resolve, 0));
  expect(onPrepared).toHaveBeenCalledOnce();
});

it("does not prepare again for contrast-only changes and can show an unchanged hidden scenario", async () => {
  const onPrepared = vi.fn();
  const onDisplayRangeChange = vi.fn();
  const onHide = vi.fn();
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    if (String(input).includes("/scenarios/dimensions")) {
      return Promise.resolve(jsonResponse(dimensions));
    }
    return Promise.resolve(jsonResponse(prepared()));
  });
  const { rerender } = render(
    <ScenarioBuilder
      {...props}
      onPrepared={onPrepared}
      onDisplayRangeChange={onDisplayRangeChange}
      onHide={onHide}
    />,
  );
  await screen.findAllByRole("slider");
  fireEvent.click(screen.getByRole("button", { name: "Все поровну" }));
  fireEvent.click(screen.getByRole("button", { name: "Показать сценарий" }));
  await waitFor(() => expect(onPrepared).toHaveBeenCalledOnce());
  rerender(
    <ScenarioBuilder
      {...props}
      active
      activeHeatmap={prepared()}
      onPrepared={onPrepared}
      onDisplayRangeChange={onDisplayRangeChange}
      onHide={onHide}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Средний" }));
  expect(onDisplayRangeChange).toHaveBeenCalledWith({ min: 25, max: 100 });
  expect(fetchMock.mock.calls.filter(([input]) => String(input).includes("/heatmap/prepare"))).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "Скрыть" }));
  expect(onHide).toHaveBeenCalledOnce();
  rerender(
    <ScenarioBuilder
      {...props}
      active={false}
      activeHeatmap={null}
      onPrepared={onPrepared}
      onDisplayRangeChange={onDisplayRangeChange}
      onHide={onHide}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Показать сценарий" }));
  await waitFor(() => expect(onPrepared).toHaveBeenCalledTimes(2));
});

it("blocks manual 50 m below z13 and derives district-only display quantiles", async () => {
  const onDisplayRangeChange = vi.fn();
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    if (String(input).includes("/scenarios/dimensions")) return Promise.resolve(jsonResponse(dimensions));
    if (String(input).includes("/scoring/distribution")) {
      return Promise.resolve(jsonResponse({
        grid_version: "spb-square-200m-v1",
        scoring_signature: "a".repeat(64),
        cell_count: 1234,
        p10: 31,
        p25: 45,
        p50: 58,
        p75: 70,
        p90: 84,
      }));
    }
    return Promise.resolve(jsonResponse(prepared()));
  });
  render(
    <ScenarioBuilder
      {...props}
      active
      activeHeatmap={prepared()}
      districtIds={["00000000-0000-0000-0000-000000000001"]}
      onDisplayRangeChange={onDisplayRangeChange}
    />,
  );
  await screen.findAllByRole("slider");
  expect(screen.getByRole("button", { name: "50 м" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Все поровну" }));
  fireEvent.click(screen.getByRole("button", { name: "По району" }));
  expect(await screen.findAllByText("Сравнение внутри выбранного района")).toHaveLength(2);
  await waitFor(() => expect(onDisplayRangeChange).toHaveBeenCalledWith({ min: 31, max: 84 }));
});
