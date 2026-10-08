import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { PreparedHeatmap } from "../api/heatmap";
import { HeatmapControl } from "./HeatmapControl";

const profiles = Array.from({ length: 12 }, (_, index) => ({
  metric_key: `test.metric_${index}.distance_m`,
  normalization_version: "1",
  label: `Показатель ${index + 1}`,
  method: "piecewise_linear",
  points: [
    { raw_value: 0, score: 100 },
    { raw_value: 1000, score: 0 },
  ],
  checksum: String(index).padStart(64, "0"),
}));

const prepared: PreparedHeatmap = {
  grid_version: "spb-square-200m-v1",
  weights: { "test.metric_0.distance_m": 100 },
  scoring_signature: "a".repeat(64),
  spec: "opaque-spec",
  cell_count: 36292,
  min: 0,
  max: 100,
  mean: 50,
  tile_url_template: "/api/analysis/heatmap/tiles/signature/{z}/{x}/{y}.mvt?spec=opaque",
  delivery_version: "heatmap-mvt-v1",
};

const response = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });

afterEach(() => vi.restoreAllMocks());

it("starts off with no implicit metric and exposes all twelve profiles", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(profiles));
  render(
    <HeatmapControl
      activeHeatmap={null}
      tileError={null}
      onPrepared={vi.fn()}
      onHide={vi.fn()}
    />,
  );

  const selector = await screen.findByRole("combobox", {
    name: "Показатель тепловой карты",
  });
  expect(selector).toHaveValue("");
  expect(screen.getByRole("button", { name: "Показать" })).toBeDisabled();
  expect(screen.getAllByRole("option")).toHaveLength(13);
  expect(screen.queryByLabelText("Легенда тепловой карты")).not.toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledOnce();
});

it("prepares one explicit weight on the resolved grid, shows the active legend, and hides", async () => {
  const onPrepared = vi.fn();
  const onHide = vi.fn();
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(response(profiles))
    .mockResolvedValueOnce(response(prepared));
  const { rerender } = render(
    <HeatmapControl
      activeHeatmap={null}
      tileError={null}
      onPrepared={onPrepared}
      onHide={onHide}
    />,
  );

  fireEvent.change(
    await screen.findByRole("combobox", { name: "Показатель тепловой карты" }),
    { target: { value: profiles[0].metric_key } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Показать" }));
  await waitFor(() => expect(onPrepared).toHaveBeenCalledWith(prepared));
  const prepareCall = fetchMock.mock.calls[1];
  expect(prepareCall[0]).toBe("/api/analysis/heatmap/prepare");
  expect(JSON.parse(String((prepareCall[1] as RequestInit).body))).toEqual({
    grid_version: "spb-square-200m-v1",
    weights: { [profiles[0].metric_key]: 100 },
  });

  rerender(
    <HeatmapControl
      activeHeatmap={prepared}
      tileError={null}
      onPrepared={onPrepared}
      onHide={onHide}
    />,
  );
  const legend = screen.getByLabelText("Легенда тепловой карты");
  for (const value of ["40", "55", "70", "85", "100"]) {
    expect(legend).toHaveTextContent(value);
  }
  expect(legend).toHaveTextContent("Баллы ниже 40");
  expect(legend).toHaveTextContent("хуже");
  expect(legend).toHaveTextContent("лучше");
  fireEvent.click(screen.getByRole("button", { name: "Скрыть" }));
  expect(onHide).toHaveBeenCalledOnce();
});

it("changes display contrast without preparing new data", async () => {
  const onDisplayRangeChange = vi.fn();
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(profiles));
  render(
    <HeatmapControl
      activeHeatmap={prepared}
      tileError={null}
      onPrepared={vi.fn()}
      onHide={vi.fn()}
      onDisplayRangeChange={onDisplayRangeChange}
    />,
  );

  await screen.findByRole("combobox", { name: "Показатель тепловой карты" });
  fireEvent.click(screen.getByRole("button", { name: "Средний" }));
  expect(onDisplayRangeChange).toHaveBeenCalledWith({ min: 25, max: 100 });
  expect(fetchMock).toHaveBeenCalledOnce();
});

it("prepares the real 50 m grid when detailed resolution is selected", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(response(profiles))
    .mockResolvedValueOnce(response({ ...prepared, grid_version: "spb-square-50m-v1" }));
  render(
    <HeatmapControl
      activeHeatmap={null}
      tileError={null}
      onPrepared={vi.fn()}
      onHide={vi.fn()}
      zoom={14}
    />,
  );

  fireEvent.change(
    await screen.findByRole("combobox", { name: "Показатель тепловой карты" }),
    { target: { value: profiles[0].metric_key } },
  );
  fireEvent.click(screen.getByRole("button", { name: "50 м" }));
  fireEvent.click(screen.getByRole("button", { name: "Показать" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body))).toEqual({
    grid_version: "spb-square-50m-v1",
    weights: { [profiles[0].metric_key]: 100 },
  });
});

it("reports a prepare failure without removing an existing overlay", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(response(profiles))
    .mockResolvedValueOnce(response({ detail: "unavailable" }, 503));
  const onPrepared = vi.fn();
  render(
    <HeatmapControl
      activeHeatmap={prepared}
      tileError={null}
      onPrepared={onPrepared}
      onHide={vi.fn()}
    />,
  );
  fireEvent.change(
    await screen.findByRole("combobox", { name: "Показатель тепловой карты" }),
    { target: { value: profiles[1].metric_key } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Показать" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Не удалось подготовить тепловую карту",
  );
  expect(onPrepared).not.toHaveBeenCalled();
  expect(screen.getByLabelText("Легенда тепловой карты")).toBeInTheDocument();
});
