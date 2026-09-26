import { afterEach, describe, expect, it, vi } from "vitest";
import {
  buildMapFeaturesUrl,
  fetchMapFeatures,
  guardBbox,
  LatestMapRequest,
  type MapFeatureRequest,
} from "./mapApi";
import type { CatalogFeatureCollection } from "./mapTypes";

const emptyCollection: CatalogFeatureCollection = { type: "FeatureCollection", features: [] };

describe("mapApi", () => {
  afterEach(() => vi.restoreAllMocks());

  it("guards backend bbox limits", () => {
    expect(guardBbox({ minLon: 30, minLat: 59, maxLon: 30.2, maxLat: 59.1 })).toEqual({
      valid: true,
      bbox: "30,59,30.2,59.1",
    });
    expect(guardBbox({ minLon: 30, minLat: 59, maxLon: 30.6, maxLat: 59.1 })).toEqual({
      valid: false,
      reason: "span",
    });
    expect(guardBbox({ minLon: 30, minLat: 59, maxLon: 30.5, maxLat: 59.25 })).toEqual({
      valid: false,
      reason: "area",
    });
    expect(guardBbox({ minLon: 31, minLat: 59, maxLon: 30, maxLat: 60 })).toEqual({
      valid: false,
      reason: "order",
    });
  });

  it("builds one encoded request for all active categories", () => {
    const url = new URL(
      buildMapFeaturesUrl({
        bounds: { minLon: 30.3, minLat: 59.93, maxLon: 30.32, maxLat: 59.945 },
        categories: ["education.school", "nature.park"],
      }),
      "http://localhost",
    );

    expect(url.pathname).toBe("/api/map/features");
    expect(url.searchParams.get("categories")).toBe("education.school,nature.park");
    expect(url.searchParams.get("limit")).toBe("5000");
    expect(url.searchParams.has("districts")).toBe(false);
  });

  it("adds one or multiple authoritative district UUIDs to the same map request", () => {
    const baseRequest = {
      bounds: { minLon: 30.3, minLat: 59.93, maxLon: 30.32, maxLat: 59.945 },
      categories: ["nature.park"],
    };
    const first = "161ba369-c548-5569-9cc2-679522090220";
    const second = "230bcc6e-fb6a-5172-afe6-81f0736fb77b";

    const one = new URL(
      buildMapFeaturesUrl({ ...baseRequest, districtIds: [first] }),
      "http://localhost",
    );
    const many = new URL(
      buildMapFeaturesUrl({ ...baseRequest, districtIds: [first, second] }),
      "http://localhost",
    );

    expect(one.searchParams.get("districts")).toBe(first);
    expect(many.searchParams.get("districts")).toBe(`${first},${second}`);
    expect(many.searchParams.get("bbox")).toBe("30.3,59.93,30.32,59.945");
    expect(many.searchParams.get("categories")).toBe("nature.park");
    expect(many.searchParams.get("limit")).toBe("5000");
  });

  it("validates GeoJSON and preserves feature-limit machine errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ type: "FeatureCollection", features: "invalid" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const request = {
      bounds: { minLon: 30.3, minLat: 59.93, maxLon: 30.32, maxLat: 59.945 },
      categories: ["nature.park"],
    };
    await expect(fetchMapFeatures(request)).rejects.toMatchObject({
      message: "Map API returned an invalid GeoJSON response",
    });

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({ detail: { code: "feature_limit_exceeded", message: "too many" } }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    );
    await expect(fetchMapFeatures(request)).rejects.toMatchObject({
      status: 422,
      code: "feature_limit_exceeded",
    });
  });

  it("aborts the previous request and ignores a late stale response", async () => {
    const resolvers: Array<(value: CatalogFeatureCollection) => void> = [];
    const fetcher = vi.fn(
      (requestValue: MapFeatureRequest, signalValue?: AbortSignal) => {
        void requestValue;
        void signalValue;
        return new Promise<CatalogFeatureCollection>((resolve) => {
          resolvers.push(resolve);
        });
      },
    );
    const runner = new LatestMapRequest(fetcher);
    const successes: CatalogFeatureCollection[] = [];
    const request = {
      bounds: { minLon: 30.3, minLat: 59.93, maxLon: 30.32, maxLat: 59.945 },
      categories: ["nature.park"],
    };

    const first = runner.run(request, (value) => successes.push(value), vi.fn());
    const firstSignal = fetcher.mock.calls[0]?.[1];
    const secondRequest = { ...request, districtIds: ["district-b"] };
    const second = runner.run(secondRequest, (value) => successes.push(value), vi.fn());
    expect(firstSignal?.aborted).toBe(true);
    expect(fetcher.mock.calls[1]?.[0]).toEqual(secondRequest);

    const lateCollection: CatalogFeatureCollection = {
      type: "FeatureCollection",
      features: [],
    };
    resolvers[0](lateCollection);
    resolvers[1](emptyCollection);
    await Promise.all([first, second]);

    expect(successes).toEqual([emptyCollection]);
  });
});
