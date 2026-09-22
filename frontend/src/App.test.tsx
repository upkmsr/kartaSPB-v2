import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

describe("App", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the desktop GIS shell", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "ready",
          database: { status: "ready", detail: null },
          postgis: { status: "ready", detail: "3.5.0" },
          migrations: { status: "ready", detail: "20260922_0001" },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    render(<App />);

    expect(screen.getByRole("heading", { name: "KARTASPB" })).toBeInTheDocument();
    expect(screen.getByLabelText("Панель инструментов")).toBeInTheDocument();
    expect(screen.getByLabelText("Рабочая область карты")).toBeInTheDocument();
    expect(screen.getByText("Пространственные данные появятся здесь")).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText("READY")).toHaveLength(2));
  });

  it("shows offline state when the backend cannot be reached", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network unavailable"));

    render(<App />);

    await waitFor(() => expect(screen.getAllByText("OFFLINE")).toHaveLength(2));
  });
});
