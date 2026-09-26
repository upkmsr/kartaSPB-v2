import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, it, vi } from "vitest";
import type { District } from "../api/districts";
import { DistrictSection, type DistrictLoadState } from "./DistrictSection";

const districts: District[] = Array.from({ length: 18 }, (_, index) => ({
  id: `00000000-0000-0000-0000-${String(index + 1).padStart(12, "0")}`,
  name: `Район ${index + 1}`,
  slug: `district-${index + 1}`,
  display_order: index + 1,
  bbox: [30, 59, 30.1, 59.1],
}));

function SelectionHarness() {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  return (
    <DistrictSection
      state={{ status: "loaded", districts }}
      selectedDistrictIds={selected}
      onToggle={(id) =>
        setSelected((current) => {
          const next = new Set(current);
          if (next.has(id)) next.delete(id);
          else next.add(id);
          return next;
        })
      }
      onClear={() => setSelected(new Set())}
      onLocate={vi.fn()}
      onLocateSelected={vi.fn()}
      onRetry={vi.fn()}
    />
  );
}

it("renders 18 backend rows and supports 0, 1, N, unselect, and clear", () => {
  render(<SelectionHarness />);

  expect(screen.getAllByRole("checkbox")).toHaveLength(18);
  expect(screen.getByText("Без ограничений")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("checkbox", { name: "Район 1" }));
  expect(screen.getByText("1 выбрано")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox", { name: "Район 2" }));
  expect(screen.getByText("2 выбрано")).toBeInTheDocument();

  const collapse = screen.getByRole("button", { name: /^Районы/ });
  expect(collapse).toHaveAttribute("aria-expanded", "true");
  fireEvent.click(collapse);
  expect(collapse).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
  expect(screen.getByText("2 выбрано")).toBeInTheDocument();

  fireEvent.click(collapse);
  expect(collapse).toHaveAttribute("aria-expanded", "true");
  expect(screen.getAllByRole("checkbox")).toHaveLength(18);
  expect(screen.getByRole("checkbox", { name: "Район 1" })).toBeChecked();
  expect(screen.getByRole("checkbox", { name: "Район 2" })).toBeChecked();

  fireEvent.click(screen.getByRole("checkbox", { name: "Район 1" }));
  expect(screen.getByText("1 выбрано")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Все районы" }));
  expect(screen.getByText("Без ограничений")).toBeInTheDocument();
}, 10_000);

it.each<[DistrictLoadState, string]>([
  [{ status: "loading" }, "Загружаем районы…"],
  [{ status: "loaded", districts: [] }, "Районы пока недоступны."],
])("renders scoped district state", (state, copy) => {
  render(
    <DistrictSection
      state={state}
      selectedDistrictIds={new Set()}
      onToggle={vi.fn()}
      onClear={vi.fn()}
      onLocate={vi.fn()}
      onLocateSelected={vi.fn()}
      onRetry={vi.fn()}
    />,
  );
  expect(screen.getByText(copy)).toBeInTheDocument();
});

it("offers retry after a district API failure", () => {
  const onRetry = vi.fn();
  render(
    <DistrictSection
      state={{ status: "error" }}
      selectedDistrictIds={new Set()}
      onToggle={vi.fn()}
      onClear={vi.fn()}
      onLocate={vi.fn()}
      onLocateSelected={vi.fn()}
      onRetry={onRetry}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Повторить" }));
  expect(onRetry).toHaveBeenCalledOnce();
});
