import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { InfluenceInspectorCard } from "./InfluenceInspectorCard";

it("reports independent scores, thresholds, visibility, and immutable runs", () => {
  render(
    <InfluenceInspectorCard
      inspection={{
        cellId: "spb-square-50m-v1:1:2",
        scores: [
          {
            metricKey: "education.school.accessibility_index",
            score: 71.25,
            minimumScore: 70,
            scoreRunId: "aaaaaaaa-0000-0000-0000-000000000001",
          },
          {
            metricKey: "nature.park.accessibility_index",
            score: 39.5,
            minimumScore: 40,
            scoreRunId: "bbbbbbbb-0000-0000-0000-000000000001",
          },
        ],
      }}
      onClose={vi.fn()}
    />,
  );
  expect(screen.getByText("Школы")).toBeInTheDocument();
  expect(screen.getByText("Парки")).toBeInTheDocument();
  expect(screen.getByText("порог 70 · видим")).toBeInTheDocument();
  expect(screen.getByText("порог 40 · скрыт")).toBeInTheDocument();
  expect(screen.getByText("71.3")).toBeInTheDocument();
  expect(screen.getByText(/immutable run aaaaaaaa/)).toBeInTheDocument();
});
