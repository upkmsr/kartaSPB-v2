import { describe, expect, it, vi } from "vitest";
import {
  buildSearchUrl,
  fetchSearchResults,
  LatestSearchRequest,
  normalizeSearchQuery,
  type SearchResult,
} from "./search";

const result: SearchResult = {
  id: "c49e54e1-3481-4b07-9f81-0b161b57b62b",
  name: "Озерки",
  categories: ["transport.stop"],
  object_kind: "feature",
  geometry_type: "Point",
  representative_point: { type: "Point", coordinates: [30.3, 60] },
  bbox: [30.3, 60, 30.3, 60],
};

describe("search API", () => {
  it("normalizes query and builds 0/1/N scoped requests", () => {
    expect(normalizeSearchQuery("  ЁЛОЧНАЯ   Аптека ")).toBe("елочная аптека");
    const unscoped = new URL(buildSearchUrl({ query: "невский" }), "http://localhost");
    expect(unscoped.searchParams.get("q")).toBe("невский");
    expect(unscoped.searchParams.get("limit")).toBe("20");
    expect(unscoped.searchParams.has("categories")).toBe(false);
    expect(unscoped.searchParams.has("districts")).toBe(false);

    const scoped = new URL(
      buildSearchUrl({
        query: "аптека",
        categoryKeys: ["healthcare.pharmacy", "transport.stop"],
        districtIds: ["district-a", "district-b"],
      }),
      "http://localhost",
    );
    expect(scoped.searchParams.get("categories")).toBe(
      "healthcare.pharmacy,transport.stop",
    );
    expect(scoped.searchParams.get("districts")).toBe("district-a,district-b");
  });

  it("rejects out-of-contract queries before a request", () => {
    expect(() => buildSearchUrl({ query: "не" })).toThrow(/3-100/);
    expect(() => buildSearchUrl({ query: "x".repeat(101) })).toThrow(/3-100/);
  });

  it("validates the frozen result contract", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ type: "SearchResults", results: [result] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(fetchSearchResults({ query: "озерки" })).resolves.toEqual([result]);

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ type: "SearchResults", results: [{ id: "broken" }] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(fetchSearchResults({ query: "озерки" })).rejects.toThrow(
      "invalid response",
    );
  });

  it("aborts the previous request and ignores its late response", async () => {
    const resolvers: Array<(results: SearchResult[]) => void> = [];
    const signals: AbortSignal[] = [];
    const fetcher = vi.fn((_request, signal?: AbortSignal) => {
      if (signal) signals.push(signal);
      return new Promise<SearchResult[]>((resolve) => resolvers.push(resolve));
    });
    const latest = new LatestSearchRequest(fetcher);
    const successes: SearchResult[][] = [];

    const first = latest.run({ query: "невский" }, (value) => successes.push(value), vi.fn());
    const second = latest.run({ query: "аптека" }, (value) => successes.push(value), vi.fn());
    expect(signals[0].aborted).toBe(true);

    resolvers[1]([result]);
    resolvers[0]([{ ...result, name: "Устаревший результат" }]);
    await Promise.all([first, second]);
    expect(successes).toEqual([[result]]);
  });
});
