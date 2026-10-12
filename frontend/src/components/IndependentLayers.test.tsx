import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { factorRegistry } from "../analysis/factorRegistry";
import type { PreparedInfluence } from "../api/influence";
import type { IndependentLayerState } from "../analysis/analysisPreferences";
import { IndependentLayers } from "./IndependentLayers";

const json = (payload: unknown) => new Response(JSON.stringify(payload), {
  status: 200,
  headers: { "Content-Type": "application/json" },
});

const dimensions = factorRegistry.map((factor) => ({
  key: factor.id,
  label: factor.label,
  group: "test",
  group_label: "Test",
  metric_key: factor.metricKey,
  display_order: factor.order,
}));

const Harness = ({ onPrepared = vi.fn() }: { onPrepared?: (value: PreparedInfluence) => void }) => {
  const [layers, setLayers] = useState<Record<string, IndependentLayerState>>({});
  const [prepared, setPrepared] = useState<PreparedInfluence | null>(null);
  return (
    <IndependentLayers
      active
      zoom={12}
      layers={layers}
      prepared={prepared}
      accentedFactorId={null}
      tileError={null}
      onLayersChange={setLayers}
      onPrepared={(value) => {
        setPrepared(value);
        onPrepared(value);
      }}
      onHide={vi.fn()}
      onAccentChange={vi.fn()}
      onObjectLayerVisibilityChange={vi.fn()}
    />
  );
};

afterEach(() => vi.restoreAllMocks());

it("renders eight registry-backed independent factors", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(json(dimensions));
  render(<Harness />);
  expect(await screen.findByRole("checkbox", { name: "Школы" })).toBeInTheDocument();
  expect(screen.getAllByRole("checkbox").filter((item) => item.getAttribute("aria-label") === null)).toHaveLength(16);
  expect(screen.getByRole("slider", { name: "Минимальный балл влияния: Парки" })).toHaveValue("40");
});

it("prepares once for enabled factors but not for threshold-only changes", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    if (String(input).includes("/scenarios/dimensions")) return Promise.resolve(json(dimensions));
    return Promise.resolve(json({
      grid_version: "spb-square-200m-v1",
      influence_signature: "a".repeat(64),
      spec: "immutable",
      cell_count: 36292,
      channels: [{
        metric_key: factorRegistry[1].metricKey,
        score_run_id: "00000000-0000-0000-0000-000000000001",
        property_name: "score_0",
      }],
      tile_url_template: "/tiles/{z}/{x}/{y}.mvt",
      delivery_version: "influence-mvt-v1",
    }));
  });
  const onPrepared = vi.fn();
  render(<Harness onPrepared={onPrepared} />);
  fireEvent.click(await screen.findByRole("checkbox", { name: "Школы" }));
  await waitFor(() => expect(onPrepared).toHaveBeenCalledOnce(), { timeout: 1200 });
  fireEvent.change(screen.getByRole("slider", { name: "Минимальный балл влияния: Школы" }), {
    target: { value: "82" },
  });
  await new Promise((resolve) => window.setTimeout(resolve, 350));
  expect(fetchMock.mock.calls.filter(([input]) => String(input).includes("/influence/prepare"))).toHaveLength(1);
  expect(screen.getByText("82")).toBeInTheDocument();
});
