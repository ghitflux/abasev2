import { render, screen } from "@testing-library/react";

import DataTable, { type DataTableColumn } from "@/components/shared/data-table";

type Row = {
  id: number;
  name: string;
  status: string;
};

const columns: DataTableColumn<Row>[] = [
  { id: "name", header: "Nome", accessor: "name" },
  { id: "status", header: "Status", accessor: "status" },
];

describe("DataTable", () => {
  it("renderiza linhas skeleton sem mostrar estado vazio quando loading=true", () => {
    const { container } = render(
      <DataTable<Row>
        columns={columns}
        data={[]}
        loading
        skeletonRows={3}
        emptyMessage="Nenhum resultado."
      />,
    );

    expect(screen.queryByText("Nenhum resultado.")).not.toBeInTheDocument();
    expect(container.querySelectorAll('[data-slot="table-row"]')).toHaveLength(4);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
    expect(container.querySelectorAll('[data-slot="table-cell"] .rounded-full').length).toBeGreaterThan(0);
  });
});
