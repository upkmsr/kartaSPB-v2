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

type HarnessProps = {
  onPrepared?: (value: PreparedInfluence) => void;
  onObjectLayerVisibilityChange?: (layerId: string, visible: boolean) => void;
  initialVisibleObjectLayerIds?: readonly string[];
};

const Harness = ({
  onPrepared = vi.fn(),
  onObjectLayerVisibilityChange = vi.fn(),
  initialVisibleObjectLayerIds = [],
}: HarnessProps) => {
  const [layers, setLayers] = useState<Record<string, IndependentLayerState>>({});
  const [prepared, setPrepared] = useState<PreparedInfluence | null>(null);
  const [visibleObjectLayerIds, setVisibleObjectLayerIds] = useState(
    new Set(initialVisibleObjectLayerIds),
  );
  return (
    <IndependentLayers
      active
      zoom={12}
      layers={layers}
      prepared={prepared}
      accentedFactorId={null}
      tileError={null}
      visibleObjectLayerIds={visibleObjectLayerIds}
      onLayersChange={setLayers}
      onPrepared={(value) => {
        setPrepared(value);
        onPrepared(value);
      }}
      onHide={vi.fn()}
      onAccentChange={vi.fn()}
      onObjectLayerVisibilityChange={(layerId, visible) => {
        setVisibleObjectLayerIds((current) => {
          const next = new Set(current);
          if (visible) next.add(layerId);
          else next.delete(layerId);
          return next;
        });
        onObjectLayerVisibilityChange(layerId, visible);
      }}
    />
  );
};

afterEach(() => vi.restoreAllMocks());

it("renders eight registry-backed independent factors", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(json(dimensions));
  render(<Harness />);
  expect(await screen.findByRole("checkbox", { name: "Показывать влияние: Школы" })).toBeInTheDocument();
  expect(screen.getAllByRole("checkbox")).toHaveLength(16);
  expect(screen.getByRole("slider", { name: "Минимальный балл влияния: Парки" })).toHaveValue("40");
});

it("keeps influence and catalog object visibility independent", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(json(dimensions));
  const onObjectLayerVisibilityChange = vi.fn();
  render(
    <Harness
      initialVisibleObjectLayerIds={["school"]}
      onObjectLayerVisibilityChange={onObjectLayerVisibilityChange}
    />,
  );
  const influence = await screen.findByRole("checkbox", {
    name: "Показывать влияние: Школы",
  });
  const objects = screen.getByRole("checkbox", { name: "Показывать объекты: Школы" });
  expect(influence).not.toBeChecked();
  expect(objects).toBeChecked();

  fireEvent.click(influence);
  expect(influence).toBeChecked();
  expect(objects).toBeChecked();
  expect(onObjectLayerVisibilityChange).not.toHaveBeenCalled();

  fireEvent.click(objects);
  expect(objects).not.toBeChecked();
  expect(influence).toBeChecked();
  expect(onObjectLayerVisibilityChange).toHaveBeenCalledWith("school", false);
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
  fireEvent.click(await screen.findByRole("checkbox", { name: "Показывать влияние: Школы" }));
  await waitFor(() => expect(onPrepared).toHaveBeenCalledOnce(), { timeout: 1200 });
  fireEvent.change(screen.getByRole("slider", { name: "Минимальный балл влияния: Школы" }), {
    target: { value: "82" },
  });
  await new Promise((resolve) => window.setTimeout(resolve, 350));
  expect(fetchMock.mock.calls.filter(([input]) => String(input).includes("/influence/prepare"))).toHaveLength(1);
  expect(screen.getByText("82")).toBeInTheDocument();
});
