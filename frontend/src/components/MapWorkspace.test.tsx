import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import type { MapSelection } from "../map/layerContract";
import { MapWorkspace } from "./MapWorkspace";

vi.mock("../map/MapView", () => ({
  MapView: ({
    onSelection,
    onVisibleFeatureIdsChange,
    onHeatmapCellSelect,
  }: {
    onSelection: (selection: MapSelection) => void;
    onVisibleFeatureIdsChange: (ids: ReadonlySet<string>) => void;
    onHeatmapCellSelect: (cellId: string) => void;
  }) => (
    <>
      <button
        type="button"
        onClick={() =>
          onSelection({
            kind: "canonical-object",
            objectId: "c49e54e1-3481-4b07-9f81-0b161b57b62b",
          })
        }
      >
        Выбрать аптеку
      </button>
      <button
        type="button"
        onClick={() =>
          onSelection({
            kind: "canonical-object",
            objectId: "0014437e-092b-479f-a006-10c926604682",
          })
        }
      >
        Выбрать парк
      </button>
      <button type="button" onClick={() => onVisibleFeatureIdsChange(new Set())}>
        Применить пустой scope
      </button>
      <button type="button" onClick={() => onHeatmapCellSelect("spb-square-50m-v1:1:2")}>
        Объяснить ячейку
      </button>
      <button
        type="button"
        onClick={() =>
          onSelection({
            kind: "layer-feature",
            layerId: "planning-demo",
            featureId: "zone-42",
          })
        }
      >
        Выбрать внешний слой
      </button>
    </>
  ),
}));

afterEach(() => vi.restoreAllMocks());

const WorkspaceHarness = ({
  initialSelection = null,
  inspect = false,
  heatmapSignature = "a".repeat(64),
}: {
  initialSelection?: { id: string; origin: "map" | "search" } | null;
  inspect?: boolean;
  heatmapSignature?: string;
}) => {
  const [selection, setSelection] = useState(initialSelection);
  return (
    <MapWorkspace
      visibleLayerIds={new Set()}
      autoLoad
      manualLoadSequence={0}
      districtIds={[]}
      navigationRequest={null}
      objectSelection={selection}
      activeHeatmap={inspect ? {
        grid_version: "spb-square-50m-v1",
        weights: { "education.school.accessibility_index": 100 },
        scoring_signature: heatmapSignature,
        spec: "immutable-spec",
        cell_count: 580597,
        min: 0,
        max: 100,
        mean: 50,
        tile_url_template: "/tiles/{z}/{x}/{y}.mvt",
        delivery_version: "heatmap-mvt-v1",
      } : null}
      heatmapInspectionEnabled={inspect}
      onObjectSelect={(id) => setSelection({ id, origin: "map" })}
      onObjectClose={() => setSelection(null)}
      onZoomChange={vi.fn()}
      onMapRequestStateChange={vi.fn()}
    />
  );
};

it("loads object details after feature selection and closes the card", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        id: "c49e54e1-3481-4b07-9f81-0b161b57b62b",
        name: "Озерки",
        categories: ["healthcare.pharmacy"],
        object_kind: "feature",
        geometry_type: "Point",
        properties: {},
        sources: [],
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );
  render(<WorkspaceHarness />);

  fireEvent.click(screen.getByRole("button", { name: "Выбрать аптеку" }));
  expect(globalThis.fetch).toHaveBeenCalledWith(
    "/api/objects/c49e54e1-3481-4b07-9f81-0b161b57b62b",
    expect.objectContaining({
      headers: { Accept: "application/json" },
      signal: expect.any(AbortSignal),
    }),
  );
  expect(screen.getByText("Загружаем объект")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("heading", { name: "Озерки" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "Закрыть карточку" }));
  expect(screen.queryByLabelText("Карточка объекта")).not.toBeInTheDocument();
});

it("does not route a generic layer feature into canonical ObjectDetail", () => {
  const fetchMock = vi.spyOn(globalThis, "fetch");
  render(<WorkspaceHarness />);

  fireEvent.click(screen.getByRole("button", { name: "Выбрать внешний слой" }));

  expect(fetchMock).not.toHaveBeenCalled();
  expect(screen.queryByLabelText("Карточка объекта")).not.toBeInTheDocument();
});

it("keeps the newest object card when an older details response arrives late", async () => {
  const responses: Array<(response: Response) => void> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(
    () => new Promise<Response>((resolve) => responses.push(resolve)),
  );
  render(<WorkspaceHarness />);

  fireEvent.click(screen.getByRole("button", { name: "Выбрать аптеку" }));
  fireEvent.click(screen.getByRole("button", { name: "Выбрать парк" }));

  responses[1](
    new Response(
      JSON.stringify({
        id: "0014437e-092b-479f-a006-10c926604682",
        name: "Днепропетровский сквер",
        categories: ["nature.park"],
        object_kind: "feature",
        geometry_type: "Polygon",
        properties: {},
        sources: [],
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );
  await waitFor(() =>
    expect(screen.getByRole("heading", { name: "Днепропетровский сквер" })).toBeInTheDocument(),
  );

  responses[0](
    new Response(
      JSON.stringify({
        id: "c49e54e1-3481-4b07-9f81-0b161b57b62b",
        name: "Старая аптека",
        categories: ["healthcare.pharmacy"],
        object_kind: "feature",
        geometry_type: "Point",
        properties: {},
        sources: [],
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );
  await Promise.resolve();

  expect(screen.queryByRole("heading", { name: "Старая аптека" })).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Днепропетровский сквер" })).toBeInTheDocument();
});

it("clears a selected object after it disappears from the current scope", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        id: "c49e54e1-3481-4b07-9f81-0b161b57b62b",
        name: "Озерки",
        categories: ["healthcare.pharmacy"],
        object_kind: "feature",
        geometry_type: "Point",
        properties: {},
        sources: [],
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );
  render(<WorkspaceHarness />);

  fireEvent.click(screen.getByRole("button", { name: "Выбрать аптеку" }));
  await screen.findByRole("heading", { name: "Озерки" });
  fireEvent.click(screen.getByRole("button", { name: "Применить пустой scope" }));
  expect(screen.queryByLabelText("Карточка объекта")).not.toBeInTheDocument();
});

it("keeps a search-selected object when it is absent from viewport GeoJSON", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        id: "c49e54e1-3481-4b07-9f81-0b161b57b62b",
        name: "Озерки",
        categories: ["healthcare.pharmacy"],
        object_kind: "feature",
        geometry_type: "Point",
        properties: {},
        sources: [],
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );
  render(
    <WorkspaceHarness
      initialSelection={{
        id: "c49e54e1-3481-4b07-9f81-0b161b57b62b",
        origin: "search",
      }}
    />,
  );

  await screen.findByRole("heading", { name: "Озерки" });
  fireEvent.click(screen.getByRole("button", { name: "Применить пустой scope" }));
  expect(screen.getByRole("heading", { name: "Озерки" })).toBeInTheDocument();
});

it("keeps an object-details failure scoped to ObjectCard", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("object service unavailable"));
  render(<WorkspaceHarness />);

  fireEvent.click(screen.getByRole("button", { name: "Выбрать аптеку" }));

  expect(
    await screen.findByRole("heading", { name: "Не удалось открыть карточку" }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Рабочая область карты")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Закрыть карточку" }));
  expect(screen.queryByLabelText("Карточка объекта")).not.toBeInTheDocument();
});

it("explains a clicked heatmap cell from the immutable active spec", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        grid_version: "spb-square-50m-v1",
        cell_id: "spb-square-50m-v1:1:2",
        scoring_signature: "a".repeat(64),
        score: 73.5,
        factors: [{
          metric_key: "education.school.accessibility_index",
          label: "Доступность школ",
          weight: 100,
          individual_score: 73.5,
          contribution: 73.5,
          target: {
            object_id: "c49e54e1-3481-4b07-9f81-0b161b57b62b",
            name: "Школа № 1",
            geometry_type: "POINT",
            distance_m: 412.4,
            area_m2: null,
          },
        }],
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );
  render(<WorkspaceHarness inspect />);

  fireEvent.click(screen.getByRole("button", { name: "Объяснить ячейку" }));

  await screen.findByText("73.5");
  expect(screen.getByText("Доступность школ")).toBeInTheDocument();
  expect(screen.getByText(/Школа № 1 · 412 м/)).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/analysis/scenarios/explain",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ cell_id: "spb-square-50m-v1:1:2", spec: "immutable-spec" }),
    }),
  );
});

it("clears an explanation when the active scoring signature changes", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        grid_version: "spb-square-50m-v1",
        cell_id: "spb-square-50m-v1:1:2",
        scoring_signature: "a".repeat(64),
        score: 73.5,
        factors: [],
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );
  const { rerender } = render(<WorkspaceHarness inspect />);
  fireEvent.click(screen.getByRole("button", { name: "Объяснить ячейку" }));
  await screen.findByText("73.5");

  rerender(<WorkspaceHarness inspect heatmapSignature={"b".repeat(64)} />);

  expect(screen.queryByLabelText("Почему здесь такой балл")).not.toBeInTheDocument();
});
