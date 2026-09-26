import { afterEach, describe, expect, it, vi } from "vitest";
import { combinedDistrictBbox, fetchDistricts, type District } from "./districts";

const district = (order: number): District => ({
  id: `00000000-0000-0000-0000-${String(order).padStart(12, "0")}`,
  name: `Район ${order}`,
  slug: `district-${order}`,
  display_order: order,
  bbox: [
    Number((30 + order / 100).toFixed(2)),
    59,
    Number((30.1 + order / 100).toFixed(2)),
    60,
  ],
});

describe("district API", () => {
  afterEach(() => vi.restoreAllMocks());

  it("loads districts and follows backend display order", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ districts: [district(3), district(1), district(2)] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(fetchDistricts()).resolves.toEqual([district(1), district(2), district(3)]);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/districts",
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("rejects an invalid response instead of crashing consumers", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ districts: [{ id: "broken" }] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(fetchDistricts()).rejects.toThrow("invalid response");
  });

  it("combines selected district bboxes for navigation only", () => {
    expect(combinedDistrictBbox([district(1), district(3)])).toEqual([30.01, 59, 30.13, 60]);
    expect(combinedDistrictBbox([])).toBeNull();
  });
});
