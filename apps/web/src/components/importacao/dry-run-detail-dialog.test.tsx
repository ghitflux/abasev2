import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import DryRunDetailDialog from "./dry-run-detail-dialog";
import { exportRows } from "@/lib/table-export";

jest.mock("@/lib/table-export", () => ({
  exportRows: jest.fn(),
}));

jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

const mockedExportRows = jest.mocked(exportRows);

const items = [
  {
    linha_numero: 1,
    cpf_cnpj: "23993596315",
    nome_servidor: "MARIA DE JESUS SANTANA COSTA",
    matricula_servidor: "030759-9",
    orgao_pagto_nome: "SEC. EST. ADMIN. E PREVIDEN.",
    valor_descontado: "150.00",
    status_codigo: "1",
    resultado: "baixa_efetuada",
    associado_id: 77,
    associado_nome: "Maria de Jesus Santana Costa",
    associado_status_antes: "inadimplente",
    associado_status_depois: "ativo",
    ciclo_status_antes: "aberto",
    ciclo_status_depois: "apto_a_renovar",
    ficara_apto_renovar: true,
    desconto_em_associado_inativo: false,
    categoria: "mensalidades",
  },
  {
    linha_numero: 2,
    cpf_cnpj: "15099253334",
    nome_servidor: "WERNECK NUNES DE OLIVEIRA",
    matricula_servidor: "002612-3",
    orgao_pagto_nome: "SEC. EST. FAZENDA",
    valor_descontado: "350.00",
    status_codigo: "1",
    resultado: "baixa_efetuada",
    associado_id: 78,
    associado_nome: "Werneck Nunes de Oliveira",
    associado_status_antes: "ativo",
    associado_status_depois: "ativo",
    ciclo_status_antes: "aberto",
    ciclo_status_depois: "apto_a_renovar",
    ficara_apto_renovar: true,
    desconto_em_associado_inativo: false,
    categoria: "mensalidades",
  },
];

describe("DryRunDetailDialog", () => {
  beforeEach(() => {
    mockedExportRows.mockReset();
  });

  it("filtra os aptos pela busca e exporta apenas os itens filtrados", async () => {
    const user = userEvent.setup();

    render(
      <DryRunDetailDialog
        open
        onOpenChange={() => undefined}
        title="Ficarão aptos a renovar"
        items={items}
      />,
    );

    await user.type(
      screen.getByPlaceholderText("Buscar por associado, CPF, matrícula ou órgão..."),
      "werneck",
    );

    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Werneck Nunes de Oliveira")).toBeInTheDocument();
    expect(
      within(dialog).queryByText("Maria de Jesus Santana Costa"),
    ).not.toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: /exportar/i }));
    await user.click(screen.getByRole("menuitem", { name: "CSV" }));

    expect(mockedExportRows).toHaveBeenCalledTimes(1);
    expect(mockedExportRows).toHaveBeenCalledWith(
      "csv",
      "Ficarão aptos a renovar",
      expect.stringContaining("ficarao-aptos-a-renovar"),
      expect.any(Array),
      [items[1]],
    );
  });
});
