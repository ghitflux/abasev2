import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import AdminContractEditor from "./admin-contract-editor";
import type { AdminContractEditorHandle } from "./admin-contract-editor";
import { buildCyclesPayload } from "./admin-contract-editor";
import type { AdminEditorContrato } from "@/lib/api/types";

jest.mock("@/components/custom/calendar-competencia", () => {
  function CalendarCompetenciaMock() {
    return <div data-testid="calendar-competencia" />;
  }

  CalendarCompetenciaMock.displayName = "CalendarCompetenciaMock";
  return CalendarCompetenciaMock;
});

jest.mock("@/components/custom/date-picker", () => {
  function DatePickerMock() {
    return <input aria-label="date-picker" />;
  }

  DatePickerMock.displayName = "DatePickerMock";
  return DatePickerMock;
});

jest.mock("@/components/custom/file-upload-dropzone", () => {
  function FileUploadDropzoneMock() {
    return <div data-testid="file-upload-dropzone" />;
  }

  FileUploadDropzoneMock.displayName = "FileUploadDropzoneMock";
  return FileUploadDropzoneMock;
});

jest.mock("@/components/custom/input-currency", () => {
  function InputCurrencyMock() {
    return <input aria-label="input-currency" />;
  }

  InputCurrencyMock.displayName = "InputCurrencyMock";
  return InputCurrencyMock;
});

jest.mock("@/components/custom/status-badge", () => {
  function StatusBadgeMock() {
    return <span data-testid="status-badge" />;
  }

  StatusBadgeMock.displayName = "StatusBadgeMock";
  return StatusBadgeMock;
});

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  function Wrapper({ children }: React.PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

  Wrapper.displayName = "AdminContractEditorTestWrapper";

  return render(ui, {
    wrapper: Wrapper,
  });
}

const contractFixture: AdminEditorContrato = {
  id: 101,
  codigo: "CTR-101",
  updated_at: "2026-04-01T10:00:00Z",
  status: "ativo",
  valor_bruto: "1000.00",
  valor_liquido: "900.00",
  valor_mensalidade: "75.00",
  taxa_antecipacao: "1.50",
  margem_disponivel: "250.00",
  valor_total_antecipacao: "100.00",
  doacao_associado: "0.00",
  comissao_agente: "0.00",
  data_contrato: "2025-10-05",
  data_aprovacao: "2025-10-06",
  data_primeira_mensalidade: "2025-11-01",
  mes_averbacao: "2025-10-01",
  auxilio_liberado_em: null,
  ciclos: [],
  refinanciamento_ativo: null,
  meses_nao_pagos: [],
  movimentos_financeiros_avulsos: [],
} as AdminEditorContrato;

describe("AdminContractEditor", () => {
  it("nao redispara onDirtyChange quando o pai rerenderiza com callback novo sem mudar o draft", async () => {
    const firstDirtyHandler = jest.fn();
    const secondDirtyHandler = jest.fn();
    const onPayloadRefresh = jest.fn();

    const { rerender } = renderWithQueryClient(
      <AdminContractEditor
        associadoId={55}
        contract={contractFixture}
        onPayloadRefresh={onPayloadRefresh}
        onDirtyChange={firstDirtyHandler}
      />,
    );

    await waitFor(() => {
      expect(firstDirtyHandler).toHaveBeenCalled();
    });
    const initialCallCount = firstDirtyHandler.mock.calls.length;

    rerender(
      <AdminContractEditor
        associadoId={55}
        contract={contractFixture}
        onPayloadRefresh={onPayloadRefresh}
        onDirtyChange={secondDirtyHandler}
      />,
    );

    await waitFor(() => {
      expect(firstDirtyHandler).toHaveBeenCalledTimes(initialCallCount);
    });
    expect(secondDirtyHandler).not.toHaveBeenCalled();
  });

  it("move competencia fora do ciclo para o ciclo compativel e renumera as parcelas", () => {
    const ref = React.createRef<AdminContractEditorHandle>();
    const onPayloadRefresh = jest.fn();
    const contractWithOutsideMonth: AdminEditorContrato = {
      ...contractFixture,
      ciclos: [
        {
          id: 301,
          numero: 1,
          data_inicio: "2025-10-01",
          data_fim: "2025-12-01",
          status: "aberto",
          valor_total: "225.00",
          updated_at: "2026-04-01T10:00:00Z",
          comprovantes_ciclo: [],
          termo_antecipacao: null,
          parcelas: [
            {
              id: 401,
              numero: 1,
              referencia_mes: "2025-10-01",
              valor: "75.00",
              data_vencimento: "2025-10-05",
              status: "descontado",
              data_pagamento: "2025-10-05",
              observacao: "",
              layout_bucket: "cycle",
              updated_at: "2026-04-01T10:00:00Z",
              financial_flags: {
                tem_retorno: false,
                tem_baixa_manual: false,
                tem_liquidacao: false,
              },
            },
            {
              id: 403,
              numero: 3,
              referencia_mes: "2025-12-01",
              valor: "75.00",
              data_vencimento: "2025-12-05",
              status: "em_previsao",
              data_pagamento: null,
              observacao: "",
              layout_bucket: "cycle",
              updated_at: "2026-04-01T10:00:00Z",
              financial_flags: {
                tem_retorno: false,
                tem_baixa_manual: false,
                tem_liquidacao: false,
              },
            },
          ],
        },
      ],
      meses_nao_pagos: [
        {
          id: 402,
          numero: 2,
          referencia_mes: "2025-11-01",
          valor: "75.00",
          data_vencimento: "2025-11-05",
          status: "nao_descontado",
          data_pagamento: null,
          observacao: "Competência movida para fora do ciclo.",
          layout_bucket: "unpaid",
          updated_at: "2026-04-01T10:00:00Z",
          financial_flags: {
            tem_retorno: false,
            tem_baixa_manual: false,
            tem_liquidacao: false,
          },
        },
      ],
      movimentos_financeiros_avulsos: [],
    };

    renderWithQueryClient(
      <AdminContractEditor
        ref={ref}
        associadoId={55}
        contract={contractWithOutsideMonth}
        onPayloadRefresh={onPayloadRefresh}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Mover para ciclo compatível/i }));

    expect(
      ref.current?.getPendingChanges()?.cycles?.parcelas.map((parcela) => ({
        referencia_mes: parcela.referencia_mes,
        numero: parcela.numero,
        layout_bucket: parcela.layout_bucket,
      })),
    ).toEqual([
      {
        referencia_mes: "2025-10-01",
        numero: 1,
        layout_bucket: "cycle",
      },
      {
        referencia_mes: "2025-11-01",
        numero: 2,
        layout_bucket: "cycle",
      },
      {
        referencia_mes: "2025-12-01",
        numero: 3,
        layout_bucket: "cycle",
      },
    ]);
  });

  it("gera ciclo ancora automatico quando nao ha ciclos e existem parcelas fora do ciclo", () => {
    const contractWithoutCycles: AdminEditorContrato = {
      ...contractFixture,
      ciclos: [],
      meses_nao_pagos: [
        {
          id: 901,
          numero: 1,
          referencia_mes: "2026-02-01",
          valor: "75.00",
          data_vencimento: "2026-02-05",
          status: "nao_descontado",
          data_pagamento: null,
          observacao: "",
          layout_bucket: "unpaid",
          updated_at: "2026-04-01T10:00:00Z",
          financial_flags: {
            tem_retorno: false,
            tem_baixa_manual: false,
            tem_liquidacao: false,
          },
        },
      ],
      movimentos_financeiros_avulsos: [],
    };
    const payload = buildCyclesPayload(contractWithoutCycles as any);

    expect(payload.cycles).toEqual([
      {
        id: null,
        client_key: "auto-fallback-cycle-1",
        numero: 1,
        data_inicio: "2026-02-01",
        data_fim: "2026-02-01",
        status: "aberto",
        valor_total: "75.00",
      },
    ]);
    expect(payload.parcelas[0]?.cycle_ref).toBe("auto-fallback-cycle-1");
  });
});
