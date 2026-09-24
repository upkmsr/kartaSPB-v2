import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { defaultVisibleLayerIds } from "../map/layerRegistry";
import { LayerControl } from "./LayerControl";

it("renders visibility state, min-zoom hints, and layer toggles", () => {
  const onToggle = vi.fn();
  render(
    <LayerControl visibleLayerIds={defaultVisibleLayerIds()} zoom={13} onToggle={onToggle} />,
  );

  expect(screen.getByRole("checkbox", { name: /Школы/ })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: /Адм. границы/ })).not.toBeChecked();
  expect(screen.getByText("с z16")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox", { name: /Дороги/ }));
  expect(onToggle).toHaveBeenCalledWith("road");
});
