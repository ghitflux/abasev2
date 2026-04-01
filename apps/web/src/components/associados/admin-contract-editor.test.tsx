import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";

import AdminContractEditor from "./admin-contract-editor";
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
});
