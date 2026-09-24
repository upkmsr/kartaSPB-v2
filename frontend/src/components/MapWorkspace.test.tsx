import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MapWorkspace } from "./MapWorkspace";

vi.mock("../map/MapView", () => ({
  MapView: ({ onFeatureSelect }: { onFeatureSelect: (id: string) => void }) => (
    <button type="button" onClick={() => onFeatureSelect("c49e54e1-3481-4b07-9f81-0b161b57b62b")}>
      Выбрать аптеку
    </button>
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
  expect(screen.getByText("Загружаем объект")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("heading", { name: "Озерки" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "Закрыть карточку" }));
  expect(screen.queryByLabelText("Карточка объекта")).not.toBeInTheDocument();
});
