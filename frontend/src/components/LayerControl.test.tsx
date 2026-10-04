import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { defaultVisibleLayerIds } from "../map/layerRegistry";
import { LayerControl } from "./LayerControl";

it("renders visibility state, min-zoom hints, and layer toggles", () => {
  const onToggle = vi.fn();
  render(
    <LayerControl
      visibleLayerIds={defaultVisibleLayerIds()}
      zoom={13}
      autoLoad
      requestState={{ status: "idle" }}
      onToggle={onToggle}
      onAutoLoadChange={vi.fn()}
      onLoadObjects={vi.fn()}
      onReset={vi.fn()}
    />,
  );

  expect(screen.getByRole("checkbox", { name: /Школы/ })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: /Адм. границы/ })).not.toBeChecked();
  expect(screen.getByText("с z16")).toBeInTheDocument();
  expect(screen.getByText("Городские объекты")).toBeInTheDocument();
  expect(screen.getByText("Аналитика")).toBeInTheDocument();
  expect(screen.getByRole("checkbox", { name: /Аналитическая сетка/ })).not.toBeChecked();
  fireEvent.click(screen.getByRole("checkbox", { name: /Дороги/ }));
  expect(onToggle).toHaveBeenCalledWith("road");
});

it("offers one explicit load while automatic loading is disabled and pending", () => {
  const onLoadObjects = vi.fn();
  const onAutoLoadChange = vi.fn();
  const onReset = vi.fn();
  render(
    <LayerControl
      visibleLayerIds={defaultVisibleLayerIds()}
      zoom={12}
      autoLoad={false}
      requestState={{
        status: "pending-manual-load",
        loadableLayerIds: ["water", "park", "hospital"],
      }}
      onToggle={vi.fn()}
      onAutoLoadChange={onAutoLoadChange}
      onLoadObjects={onLoadObjects}
      onReset={onReset}
    />,
  );

  expect(screen.getByText("Карта изменена — загрузите объекты")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Загрузить объекты" }));
  expect(onLoadObjects).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByRole("checkbox", { name: "Автоматически загружать объекты" }));
  expect(onAutoLoadChange).toHaveBeenCalledWith(true);
  fireEvent.click(screen.getByRole("button", { name: "Сбросить настройки" }));
  expect(onReset).toHaveBeenCalledOnce();
});

it("keeps intent checked below minZoom and reports visibility at minZoom", () => {
  const { rerender } = render(
    <LayerControl
      visibleLayerIds={new Set(["road"])}
      zoom={15.9}
      autoLoad
      requestState={{ status: "waiting-for-zoom", waitingLayerIds: ["road"] }}
      onToggle={vi.fn()}
      onAutoLoadChange={vi.fn()}
      onLoadObjects={vi.fn()}
      onReset={vi.fn()}
    />,
  );
  expect(screen.getByRole("checkbox", { name: /Дороги/ })).toBeChecked();
  expect(screen.getByText("с z16")).toBeInTheDocument();

  rerender(
    <LayerControl
      visibleLayerIds={new Set(["road"])}
      zoom={16}
      autoLoad
      requestState={{
        status: "ready",
        featureCount: 2,
        durationMs: 10,
        loadedLayerIds: ["road"],
      }}
      onToggle={vi.fn()}
      onAutoLoadChange={vi.fn()}
      onLoadObjects={vi.fn()}
      onReset={vi.fn()}
    />,
  );
  expect(screen.getByText("видим")).toBeInTheDocument();
});
