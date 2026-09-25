import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MapWorkspace } from "./MapWorkspace";

vi.mock("../map/MapView", () => ({
  MapView: ({ onFeatureSelect }: { onFeatureSelect: (id: string) => void }) => (
    <>
      <button type="button" onClick={() => onFeatureSelect("c49e54e1-3481-4b07-9f81-0b161b57b62b")}>
        Выбрать аптеку
      </button>
      <button type="button" onClick={() => onFeatureSelect("0014437e-092b-479f-a006-10c926604682")}>
        Выбрать парк
      </button>
    </>
  ),
}));

afterEach(() => vi.restoreAllMocks());

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
  render(<MapWorkspace visibleLayerIds={new Set()} onZoomChange={vi.fn()} />);

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
  render(<MapWorkspace visibleLayerIds={new Set()} onZoomChange={vi.fn()} />);

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
