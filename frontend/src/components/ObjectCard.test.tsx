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
          facility: {
            id: "9f3f27a5-950f-5c24-adce-5fe4db2c36c7",
            category_key: "healthcare.clinic",
            representative_object_id: "c49e54e1-3481-4b07-9f81-0b161b57b62b",
            display_object_id: "0014437e-092b-479f-a006-10c926604682",
            analysis_object_id: "c49e54e1-3481-4b07-9f81-0b161b57b62b",
            members: [
              {
                canonical_id: "c49e54e1-3481-4b07-9f81-0b161b57b62b",
                geometry_role: "POINT",
                source_type: "node",
                source_object_id: "339394777",
              },
              {
                canonical_id: "0014437e-092b-479f-a006-10c926604682",
                geometry_role: "BUILDING",
                source_type: "way",
                source_object_id: "751143097",
              },
            ],
          },
        },
      }}
    />,
  );

  expect(screen.getByRole("heading", { name: "Озерки" })).toBeInTheDocument();
  expect(screen.getByText("Аптеки")).toBeInTheDocument();
  expect(screen.getAllByText("node 339394777")).toHaveLength(2);
  expect(screen.getByLabelText("Логическое представление")).toBeInTheDocument();
  expect(screen.getByText("2 исходных объекта")).toBeInTheDocument();
  expect(screen.getByText("BUILDING")).toBeInTheDocument();
  expect(screen.queryByText(/payload_hash|import_run|hidden/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Закрыть карточку" }));
  expect(onClose).toHaveBeenCalledOnce();
});
