import { afterEach, describe, expect, it, vi } from "vitest";
import {
  combinedDistrictBbox,
  fetchDistrictGeometry,
  fetchDistricts,
  LatestDistrictGeometryRequest,
  type District,
  type DistrictGeometryFeatureCollection,
} from "./districts";

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

  it("loads one combined exact-geometry request for selected public UUIDs", async () => {
    const collection: DistrictGeometryFeatureCollection = {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          id: district(1).id,
          properties: { id: district(1).id, name: "Район 1", slug: "district-1" },
          geometry: {
            type: "Polygon",
            coordinates: [[[30, 59], [30.1, 59], [30, 59]]],
          },
        },
        {
          type: "Feature",
          id: district(2).id,
          properties: { id: district(2).id, name: "Район 2", slug: "district-2" },
          geometry: {
            type: "MultiPolygon",
            coordinates: [[[[30, 59], [30.1, 59], [30, 59]]]],
          },
        },
      ],
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(response(collection));

    await expect(fetchDistrictGeometry([district(1).id, district(2).id])).resolves.toEqual(
      collection,
    );
    const requestUrl = new URL(String(vi.mocked(globalThis.fetch).mock.calls[0][0]), "http://localhost");
    expect(requestUrl.pathname).toBe("/api/districts/geometry");
    expect(requestUrl.searchParams.get("districts")).toBe(
      `${district(1).id},${district(2).id}`,
    );
  });

  it("does not request geometry for zero selection and rejects invalid geometry", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    await expect(fetchDistrictGeometry([])).resolves.toEqual({
      type: "FeatureCollection",
      features: [],
    });
    expect(fetchMock).not.toHaveBeenCalled();

    fetchMock.mockResolvedValue(response({ type: "FeatureCollection", features: [{ id: "bad" }] }));
    await expect(fetchDistrictGeometry([district(1).id])).rejects.toThrow("invalid response");
  });

  it("ignores stale and aborted district geometry responses", async () => {
    const resolvers: Array<(value: DistrictGeometryFeatureCollection) => void> = [];
    const fetcher = vi.fn(
      () =>
        new Promise<DistrictGeometryFeatureCollection>((resolve) => {
          resolvers.push(resolve);
        }),
    );
    const request = new LatestDistrictGeometryRequest(fetcher);
    const onSuccess = vi.fn();
    const onError = vi.fn();

    void request.run([district(1).id], onSuccess, onError);
    void request.run([district(2).id], onSuccess, onError);
    resolvers[0]({ type: "FeatureCollection", features: [] });
    await Promise.resolve();
    expect(onSuccess).not.toHaveBeenCalled();
    resolvers[1]({ type: "FeatureCollection", features: [] });
    await Promise.resolve();
    expect(onSuccess).toHaveBeenCalledOnce();

    void request.run([district(3).id], onSuccess, onError);
    request.cancel();
    resolvers[2]({ type: "FeatureCollection", features: [] });
    await Promise.resolve();
    expect(onSuccess).toHaveBeenCalledOnce();
    expect(onError).not.toHaveBeenCalled();
  });

  it("does not surface AbortError from a cancelled geometry request", async () => {
    const fetcher = vi.fn(
      (_districtIds: readonly string[], signal?: AbortSignal) =>
        new Promise<DistrictGeometryFeatureCollection>((_resolve, reject) => {
          signal?.addEventListener("abort", () =>
            reject(new DOMException("Request aborted", "AbortError")),
          );
        }),
    );
    const request = new LatestDistrictGeometryRequest(fetcher);
    const onError = vi.fn();

    const pending = request.run([district(1).id], vi.fn(), onError);
    request.cancel();
    await pending;

    expect(onError).not.toHaveBeenCalled();
  });
});

const response = (payload: unknown) =>
  new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
