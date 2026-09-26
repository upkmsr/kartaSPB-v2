import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { MapWorkspace } from "./MapWorkspace";

vi.mock("../map/MapView", () => ({
  MapView: ({
    onFeatureSelect,
    onVisibleFeatureIdsChange,
  }: {
    onFeatureSelect: (id: string) => void;
    onVisibleFeatureIdsChange: (ids: ReadonlySet<string>) => void;
  }) => (
    <>
      <button type="button" onClick={() => onFeatureSelect("c49e54e1-3481-4b07-9f81-0b161b57b62b")}>
        Выбрать аптеку
      </button>
      <button type="button" onClick={() => onFeatureSelect("0014437e-092b-479f-a006-10c926604682")}>
        Выбрать парк
      </button>
      <button type="button" onClick={() => onVisibleFeatureIdsChange(new Set())}>
        Применить пустой scope
      </button>
    </>
  ),
}));

afterEach(() => vi.restoreAllMocks());

const WorkspaceHarness = ({
  initialSelection = null,
}: {
  initialSelection?: { id: string; origin: "map" | "search" } | null;
}) => {
  const [selection, setSelection] = useState(initialSelection);
  return (
    <MapWorkspace
      visibleLayerIds={new Set()}
      districtIds={[]}
      navigationRequest={null}
      objectSelection={selection}
      onObjectSelect={(id) => setSelection({ id, origin: "map" })}
      onObjectClose={() => setSelection(null)}
      onZoomChange={vi.fn()}
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
