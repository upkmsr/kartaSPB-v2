import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { MapSettingsPanel } from "./MapSettingsPanel";

it("exposes performance and analysis-detail presets independently", () => {
  const onPerformanceProfileChange = vi.fn();
  const onAnalysisDetailChange = vi.fn();
  render(
    <MapSettingsPanel
      autoLoad
      requestState={{ status: "idle" }}
      performanceProfile="balanced"
      analysisDetail="auto"
      onAutoLoadChange={vi.fn()}
      onLoadObjects={vi.fn()}
      onReset={vi.fn()}
      onPerformanceProfileChange={onPerformanceProfileChange}
      onAnalysisDetailChange={onAnalysisDetailChange}
    />,
  );

  expect(screen.getByRole("button", { name: "Сбалансированный" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(screen.getByRole("button", { name: "Авто" })).toHaveAttribute("aria-pressed", "true");

  fireEvent.click(screen.getByRole("button", { name: "Экономичный" }));
  fireEvent.click(screen.getByRole("button", { name: "50 м" }));

  expect(onPerformanceProfileChange).toHaveBeenCalledWith("economy");
  expect(onAnalysisDetailChange).toHaveBeenCalledWith("50m");
});
