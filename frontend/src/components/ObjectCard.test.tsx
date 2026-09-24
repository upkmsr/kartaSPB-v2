import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ObjectCard } from "./ObjectCard";

it("renders canonical details and compact provenance without internals", () => {
  const onClose = vi.fn();
  render(
    <ObjectCard
      onClose={onClose}
      state={{
        status: "loaded",
        detail: {
          id: "c49e54e1-3481-4b07-9f81-0b161b57b62b",
          name: "Озерки",
          categories: ["healthcare.pharmacy"],
          object_kind: "feature",
          geometry_type: "Point",
          properties: { wheelchair: true, nested: { hidden: true } },
          sources: [
            {
              provider: "Geofabrik GmbH",
              object_type: "node",
              object_id: "339394777",
              source_version: "2026-09-21",
              geometry_quality: "raw",
            },
          ],
        },
      }}
    />,
  );

  expect(screen.getByRole("heading", { name: "Озерки" })).toBeInTheDocument();
  expect(screen.getByText("Аптеки")).toBeInTheDocument();
  expect(screen.getByText("node 339394777")).toBeInTheDocument();
  expect(screen.queryByText(/payload_hash|import_run|hidden/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Закрыть карточку" }));
  expect(onClose).toHaveBeenCalledOnce();
});
