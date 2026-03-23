// Tipos globais do app ABASE Mobile

export type User = { id: number; name: string; email: string };
export type Roles = string[];

export type Pessoa = {
  nome_razao_social: string;
  documento: string;
  email: string;
  celular: string;
  orgao_publico: string;
  cidade: string;
  uf: string;
};

export type VinculoPublico = {
  orgao_publico: string;
  situacao_servidor: string;
  matricula: string;
};

export type DadosBancarios = {
  banco: string;
  agencia: string;
  conta: string;
  tipo_conta: string;
  chave_pix: string;
};

export type Contrato = {
  codigo: string | null;
  status_contrato: string;
  prazo: number;
  parcela_valor: number;
  mensalidade?: number;
  total_financiado: number;
  data_aprovacao?: string | null;
};

export type Resumo = {
  prazo: number;
  parcela_valor: number;
  total_financiado: number;
  status_contrato: string;
  parcelas_pagas: number;
  parcelas_restantes: number;
  atraso: number;
  abertas_total: number;
  total_pago: number;
  restante: number;
  percentual_pago: number;
  elegivel_antecipacao: boolean;
  mensalidade?: number;
};

export type TermoAdesao =
  | {
      name: string;
      mime: string;
      size_bytes: number;
      uploaded_at: string | null;
      relative_path: string | null;
      url: string | null;
      origin: 'inicial' | 'reupload' | string;
    }
  | null;

export type Bootstrap = {
  pessoa: Pessoa;
  vinculo_publico: VinculoPublico;
  dados_bancarios: DadosBancarios;
  contratos: Contrato[];
  resumo: Resumo;
  proximaRef?: {
    mesLabel: string;
    dataLabel: string;
    iso?: string;
  } | null;
  termo_adesao: TermoAdesao;
  aceite_termos?: boolean;
  cadastro?: {
    auxilio1_status?: string;
    auxilio2_status?: string;
    contrato_mensalidade?: number;
  };
  whatsapps?: {
    geral?: string | null;
    juridico?: string | null;
  };
  issues?: Issue[];
  pendencias?: Issue[];
  permissions?: {
    auxilio1?: boolean;
    auxilio2?: boolean;
  };
  auxilios?: {
    auxilio1?: { allowed?: boolean; status?: string };
    auxilio2?: { allowed?: boolean; status?: string };
  };
  termos?: {
    adesao_admin_url?: string | null;
    antecipacao_admin_url?: string | null;
    adesaoUrl?: string | null;
    antecipacaoUrl?: string | null;
    adesao_user_uploaded?: boolean;
    antecipacao_user_uploaded?: boolean;
    adesaoUserUploaded?: boolean;
    antecipacaoUserUploaded?: boolean;
  };
  exists?: boolean;
  status?: string;
  basic_complete?: boolean;
  complete?: boolean;
};

export type AuthPayload = {
  user: User;
  token: string;
  refreshToken?: string | null;
  roles: Roles;
  bootstrap?: Bootstrap | null;
};

export type LoginResponse = {
  access: string;
  refresh: string;
  user: User;
  roles?: Roles;
};

export type HomeResponse = Bootstrap & {
  ok?: boolean;
  user?: User;
  roles?: Roles;
};

export type MeResponse = HomeResponse;

export type RegisterParams = {
  name: string;
  email: string;
  password: string;
  password_confirmation: string;
  terms?: boolean;
  terms_version?: string;
};

export type RegisterResponse = {
  ok: boolean;
  message?: string;
  token?: string;
  refreshToken?: string | null;
  user?: User;
  roles?: Roles;
  [key: string]: any;
};

export type PerfilData = {
  fullName: string;
  email: string;
  phone?: string;
  cpf?: string;
  cpfMasked?: string;
  descontadas: number;
  total: number;
  statusLabel: string;
  termo?: { name?: string; url?: string | null } | null;
};

// Mensalidades
export type Parcela = {
  id?: number;
  numero: number;
  referencia_mes: string;
  valor: number;
  data_vencimento: string;
  status: string;
  data_pagamento?: string | null;
  observacao?: string;
};

export type Ciclo = {
  id?: number;
  codigo?: string;
  parcelas: Parcela[];
};

// Antecipação
export type AntecipacaoItem = {
  id?: number;
  referencia_mes: string;
  valor: number;
  status: string;
  data_pagamento?: string | null;
};

// Pendências / Issues
export type Issue = {
  id?: number;
  tipo?: string;
  descricao?: string;
  status?: string;
  created_at?: string;
};

// LocalFile (para upload via FormData)
export type LocalFile = {
  uri: string;
  name: string;
  type: string;
  size?: number;
};
