export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  primary_role: string | null;
  roles: string[];
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface AuthState {
  accessToken: string;
  refreshToken: string;
  user: User;
}

export interface AssociadoMobile {
  id: number;
  nome_completo: string;
  cpf_cnpj: string;
  matricula: string;
  email: string;
  telefone: string;
  status: string;
  orgao_publico: string;
  cargo: string;
}

export interface ContratoResumo {
  id: number;
  codigo: string;
  status: string;
  prazo_meses: number;
  valor_mensalidade: string;
  data_primeira_mensalidade: string | null;
}

export interface ResumoFinanceiro {
  parcelas_pagas: number;
  parcelas_total: number;
  valor_mensalidade: string | null;
  proximo_vencimento: string | null;
  em_atraso: number;
}

export interface Pendencia {
  id: number;
  tipo: string;
  descricao: string;
  status: string;
  created_at: string;
}

export interface HomeMeResponse {
  associado: AssociadoMobile;
  contratos: ContratoResumo[];
  resumo: ResumoFinanceiro;
  pendencias: Pendencia[];
}

export interface Parcela {
  numero: number;
  referencia_mes: string;
  valor: string;
  data_vencimento: string;
  status: string;
  data_pagamento: string | null;
}

export interface Ciclo {
  id: number;
  numero: number;
  data_inicio: string;
  data_fim: string;
  status: string;
  valor_total: string;
  parcelas: Parcela[];
}

export interface MensalidadesResponse {
  ciclos: Ciclo[];
}

export interface HistoricoItem {
  referencia_mes: string;
  valor: string;
  data_pagamento: string | null;
  numero_parcela: number;
  ciclo_numero: number;
}

export interface AntecipacaoResponse {
  historico: HistoricoItem[];
}

export interface PendenciasResponse {
  pendencias: Pendencia[];
}
