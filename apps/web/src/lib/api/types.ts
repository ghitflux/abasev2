import type { Role } from "@abase/shared-types";

export type PaginatedResponse<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type PaginatedMetaResponse<T, M> = PaginatedResponse<T> & {
  meta: M;
};

export type SimpleUser = {
  id: number;
  full_name: string;
};

export type AvailableRole = {
  codigo: Role;
  nome: string;
};

export type SystemUserListItem = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  primary_role: Role | null;
  roles: Role[];
  is_active: boolean;
  must_set_password: boolean;
  date_joined: string;
  last_login: string | null;
  is_current_user: boolean;
};

export type SystemUsersMeta = {
  total: number;
  ativos: number;
  admins: number;
  troca_senha_pendente: number;
  available_roles: AvailableRole[];
};

export type SystemUserAccessUpdatePayload = {
  roles: Role[];
  is_active: boolean;
};

export type SystemUserPasswordResetPayload = {
  password: string;
  password_confirm: string;
};

export type SystemUserPasswordResetResult = {
  detail: string;
  must_set_password: boolean;
};

export type Metrica = {
  count: number;
  variacao_percentual: number;
};

export type AssociadoMetricas = {
  total: Metrica;
  ativos: Metrica;
  em_analise: Metrica;
  inativos: Metrica;
  liquidados: Metrica;
};

export type Parcela = {
  id: number;
  numero: number;
  referencia_mes: string;
  valor: string;
  data_vencimento: string;
  status: string;
  data_pagamento: string | null;
  observacao: string;
};

export type ComprovanteCiclo = {
  id: number | null;
  tipo: string;
  papel: string;
  arquivo: string;
  arquivo_referencia: string;
  arquivo_disponivel_localmente: boolean;
  tipo_referencia: string;
  nome_original: string;
  mime: string;
  size_bytes: number | null;
  data_pagamento: string | null;
  origem: string;
  created_at: string | null;
  legacy_comprovante_id: number | null;
};

export type ArquivoEvidencia = {
  id: string;
  nome: string;
  url: string;
  arquivo_referencia: string;
  arquivo_disponivel_localmente: boolean;
  tipo_referencia: string;
  origem: string;
  papel: string;
  tipo: string;
  status: string;
  competencia: string | null;
  created_at: string | null;
};

export type PagamentoInicialEvidencia = ArquivoEvidencia;

export type Ciclo = {
  id: number;
  contrato_id: number;
  contrato_codigo: string;
  contrato_status: string;
  numero: number;
  data_inicio: string;
  data_fim: string;
  status: string;
  fase_ciclo: string;
  situacao_financeira: string;
  status_visual_slug: string;
  status_visual_label: string;
  valor_total: string;
  data_ativacao_ciclo: string | null;
  origem_data_ativacao: string;
  ativacao_inferida: boolean;
  data_solicitacao_renovacao: string | null;
  data_renovacao: string | null;
  origem_renovacao: string;
  primeira_competencia_ciclo: string;
  ultima_competencia_ciclo: string;
  resumo_referencias: string;
  refinanciamento_id: number | null;
  legacy_refinanciamento_id: number | null;
  comprovantes_ciclo: ComprovanteCiclo[];
  termo_antecipacao: ComprovanteCiclo | null;
  parcelas: Parcela[];
};

export type MesNaoPago = {
  id: number;
  contrato_id: number;
  contrato_codigo: string;
  referencia_mes: string;
  valor: string;
  status: string;
  data_pagamento: string | null;
  observacao: string;
  source?: string;
};

export type AssociadoCyclesPayload = {
  ciclos: Ciclo[];
  meses_nao_pagos: MesNaoPago[];
};

export type ParcelaDetail = {
  contrato_id: number;
  contrato_codigo: string;
  cycle_number: number | null;
  numero_parcela: number | null;
  kind: "cycle" | "unpaid";
  referencia_mes: string;
  status: string;
  valor: string;
  data_vencimento: string | null;
  observacao: string;
  data_pagamento: string | null;
  data_importacao_arquivo: string | null;
  data_baixa_manual: string | null;
  data_pagamento_tesouraria: string | null;
  origem_quitacao: string;
  origem_quitacao_label: string;
  competencia_evidencias: ArquivoEvidencia[];
  documentos_ciclo: ArquivoEvidencia[];
  termo_antecipacao: ArquivoEvidencia | null;
};

export type Documento = {
  id: number;
  tipo: string;
  arquivo: string;
  arquivo_referencia: string;
  arquivo_disponivel_localmente: boolean;
  tipo_referencia: string;
  arquivo_referencia_path?: string;
  nome_original?: string;
  origem?: string;
  status: string;
  observacao: string;
  created_at?: string;
  updated_at?: string;
};

export type Contato = {
  id?: number;
  celular?: string;
  email?: string;
  orgao_publico?: string;
  situacao_servidor?: string;
  matricula_servidor?: string;
};

export type Endereco = {
  id?: number;
  cep: string;
  endereco: string;
  numero: string;
  complemento?: string;
  bairro: string;
  cidade: string;
  uf: string;
};

export type DadosBancarios = {
  id?: number;
  banco: string;
  agencia: string;
  conta: string;
  tipo_conta: string;
  chave_pix?: string;
};

export type EsteiraResumo = {
  id: number;
  etapa_atual: string;
  status: string;
  prioridade: number;
  pendencias: Array<{
    id: number;
    tipo: string;
    descricao: string;
    status: string;
    created_at: string;
  }>;
  transicoes: Array<{
    id: number;
    acao: string;
    de_status: string;
    para_status: string;
    de_situacao: string;
    para_situacao: string;
    observacao: string;
    realizado_em: string;
  }>;
  analista?: SimpleUser | null;
  coordenador?: SimpleUser | null;
  tesoureiro?: SimpleUser | null;
};

export type ContratoResumo = {
  id: number;
  codigo: string;
  valor_bruto: string;
  valor_liquido: string;
  valor_mensalidade: string;
  prazo_meses: number;
  taxa_antecipacao: string;
  margem_disponivel: string;
  valor_total_antecipacao: string;
  doacao_associado: string;
  comissao_agente: string;
  status: string;
  data_contrato: string;
  data_aprovacao: string | null;
  data_primeira_mensalidade: string | null;
  mes_averbacao: string | null;
  contato_web: boolean;
  termos_web: boolean;
  auxilio_liberado_em: string | null;
  data_primeiro_ciclo_ativado: string | null;
  origem_data_primeiro_ciclo: string;
  primeiro_ciclo_ativacao_inferida: boolean;
  status_visual_slug: string;
  status_visual_label: string;
  pagamento_inicial_status: string;
  pagamento_inicial_status_label: string;
  pagamento_inicial_valor: string | null;
  pagamento_inicial_paid_at: string | null;
  pagamento_inicial_evidencias: PagamentoInicialEvidencia[];
  status_renovacao: string;
  refinanciamento_id: number | null;
  possui_meses_nao_descontados: boolean;
  meses_nao_descontados_count: number;
  meses_nao_pagos: MesNaoPago[];
  movimentos_financeiros_avulsos: MesNaoPago[];
  ciclos: Ciclo[];
};

export type AssociadoListItem = {
  id: number;
  nome_completo: string;
  matricula: string;
  matricula_orgao?: string;
  matricula_display?: string;
  cpf_cnpj: string;
  status: string;
  status_renovacao: string;
  status_visual_slug: string;
  status_visual_label: string;
  possui_meses_nao_descontados: boolean;
  meses_nao_descontados_count: number;
  agente?: SimpleUser | null;
  ciclos_abertos: number;
  ciclos_fechados: number;
};

export type AssociadoDetail = {
  id: number;
  matricula: string;
  matricula_display?: string;
  tipo_documento: string;
  nome_completo: string;
  cpf_cnpj: string;
  rg?: string;
  orgao_expedidor?: string;
  email?: string;
  telefone?: string;
  data_nascimento?: string | null;
  profissao?: string;
  estado_civil?: string;
  orgao_publico?: string;
  matricula_orgao?: string;
  cargo?: string;
  status: string;
  status_renovacao: string;
  status_visual_slug: string;
  status_visual_label: string;
  possui_meses_nao_descontados: boolean;
  meses_nao_descontados_count: number;
  percentual_repasse?: string;
  observacao?: string;
  agente?: SimpleUser | null;
  endereco?: Endereco | null;
  dados_bancarios?: DadosBancarios | null;
  contato?: Contato | null;
  contratos: ContratoResumo[];
  documentos: Documento[];
  esteira?: EsteiraResumo | null;
  mobile_sessions?: { last_used_at: string | null; is_active: boolean }[];
};

export type EsteiraContrato = {
  codigo: string;
  associado_nome: string;
  cpf_cnpj: string;
  matricula: string;
  matricula_display?: string;
};

export type EsteiraItem = {
  id: number;
  associado_id: number;
  ordem: number;
  contrato: EsteiraContrato | null;
  data_assinatura: string | null;
  valor_disponivel: string | null;
  comissao_agente: string | null;
  status_contrato: string | null;
  status_contrato_visual_slug?: string | null;
  status_contrato_visual_label?: string | null;
  status_documentacao: string;
  contato_web: boolean;
  termos_web: boolean;
  agente?: SimpleUser | null;
  orgao_publico: string;
  documentos_count: number;
  acoes_disponiveis: string[];
  etapa_atual: string;
  status: string;
  assumido_em: string | null;
  documentos?: Documento[];
  pendencias?: Array<{
    id: number;
    tipo: string;
    descricao: string;
    status: string;
    retornado_para_agente: boolean;
    created_at: string;
    resolvida_em: string | null;
  }>;
  transicoes?: Array<{
    id: number;
    acao: string;
    de_status: string;
    para_status: string;
    de_situacao: string;
    para_situacao: string;
    observacao: string;
    realizado_em: string;
    realizado_por?: SimpleUser | null;
  }>;
};

export type AnaliseSectionKey =
  | "ver_todos"
  | "pendencias"
  | "pendencias_corrigidas"
  | "enviado_tesouraria"
  | "enviado_coordenacao"
  | "efetivados"
  | "cancelados";

export type AnaliseResumo = {
  competencia: {
    mes: string;
    inicio: string;
    fim: string;
    intervalo_label: string;
  };
  filas: Record<AnaliseSectionKey, number>;
  ajustes: {
    count: number;
    total_pago: string;
  };
  margem: {
    count: number;
    soma_margem: string;
    soma_antecipacao: string;
  };
  dados: {
    count: number;
  };
};

export type AnalisePagamentoItem = {
  id: number;
  cadastro_id: number | null;
  contrato_codigo: string;
  full_name: string;
  cpf_cnpj: string;
  agente_responsavel: string;
  status: string;
  valor_pago: string | null;
  contrato_valor_antecipacao: string | null;
  contrato_margem_disponivel: string | null;
  paid_at: string | null;
  referencia_at: string;
  created_at: string;
  created_by_name: string;
  notes: string;
};

export type AnaliseMargemItem = {
  id: number;
  associado_id: number;
  codigo: string;
  nome_completo: string;
  cpf_cnpj: string;
  agente?: SimpleUser | null;
  valor_bruto: string;
  valor_liquido: string;
  valor_mensalidade: string;
  prazo_meses: number;
  calc_trinta_bruto: string;
  calc_margem: string;
  calc_valor_antecipacao: string;
  calc_doacao_fundo: string;
  calc_pode_prosseguir: boolean;
  created_at: string;
};

export type AnaliseMargemMeta = {
  competencia: {
    mes: string;
    inicio: string;
    fim: string;
    intervalo_label: string;
  };
  totais: {
    soma_valor_bruto: string;
    soma_valor_liquido: string;
    soma_mensalidade: string;
    soma_trinta_bruto: string;
    soma_margem: string;
    soma_antecipacao: string;
    soma_doacao: string;
  };
};

export type AnaliseDadosItem = {
  id: number;
  nome_completo: string;
  cpf_cnpj: string;
  matricula: string;
  matricula_display?: string;
  agente?: SimpleUser | null;
  contrato_codigo: string | null;
  created_at: string;
};

export type PendenciaItem = {
  id: number;
  tipo: string;
  descricao: string;
  status: string;
  retornado_para_agente: boolean;
  associado_id: number;
  associado_nome: string;
  matricula: string;
  matricula_display?: string;
  cpf_cnpj: string;
  contrato_codigo: string | null;
  created_at: string;
  resolvida_em: string | null;
};

export type PendenciaResumo = {
  total: number;
  retornadas_agente: number;
  internas: number;
  associados_impactados: number;
};

export type ContratoListItem = {
  id: number;
  codigo: string;
  associado: {
    id: number;
    nome_completo: string;
    matricula: string;
    matricula_display?: string;
    cpf_cnpj: string;
    orgao_publico: string;
    matricula_orgao: string;
  };
  agente?: SimpleUser | null;
  status: string;
  status_resumido: string;
  status_contrato_visual: string;
  status_visual_slug: string;
  status_visual_label: string;
  etapa_fluxo: string;
  data_contrato: string;
  valor_mensalidade: string;
  comissao_agente: string;
  mensalidades: {
    pagas: number;
    total: number;
    descricao: string;
    apto_refinanciamento: boolean;
    refinanciamento_ativo: boolean;
  };
  auxilio_liberado_em: string | null;
  pode_solicitar_refinanciamento: boolean;
  status_renovacao: string;
  refinanciamento_id: number | null;
  possui_meses_nao_descontados: boolean;
  meses_nao_descontados_count: number;
};

export type ContratoResumoCards = {
  total: number;
  concluidos: number;
  ativos: number;
  pendentes: number;
  inadimplentes: number;
  liquidados: number;
};

export type ComprovanteResumo = {
  id: number;
  refinanciamento?: number | null;
  contrato?: number | null;
  ciclo?: number | null;
  tipo: string;
  papel: string;
  arquivo: string;
  arquivo_referencia?: string;
  arquivo_disponivel_localmente?: boolean;
  tipo_referencia?: string;
  nome_original: string;
  mime?: string;
  size_bytes?: number | null;
  data_pagamento?: string | null;
  origem?: string;
  legacy_comprovante_id?: number | null;
  enviado_por?: SimpleUser | null;
  created_at: string;
};

export type TesourariaContratoItem = {
  id: number;
  associado_id: number;
  nome: string;
  cpf_cnpj: string;
  chave_pix: string;
  codigo: string;
  data_assinatura: string;
  status: string;
  agente?: SimpleUser | null;
  agente_nome: string;
  comissao_agente: string;
  margem_disponivel: string;
  comprovantes: ComprovanteResumo[];
  dados_bancarios?: DadosBancarios | null;
  observacao_tesouraria?: string;
  etapa_atual: string;
  situacao_esteira: string;
};

export type ConfirmacaoItem = {
  id: number;
  contrato_id: number;
  associado_id: number;
  nome: string;
  cpf_cnpj: string;
  agente_nome: string;
  competencia: string;
  link_chamada: string;
  ligacao_confirmada: boolean;
  averbacao_confirmada: boolean;
  status_visual: string;
};

export type DespesaArquivo = {
  nome: string;
  url: string;
  arquivo_referencia: string;
  arquivo_disponivel_localmente: boolean;
  tipo_referencia: string;
};

export type DespesaItem = {
  id: number;
  categoria: string;
  descricao: string;
  valor: string;
  data_despesa: string;
  data_pagamento: string | null;
  status: string;
  tipo: string;
  recorrencia: string;
  recorrencia_ativa: boolean;
  observacoes: string;
  status_anexo: string;
  anexo: DespesaArquivo | null;
  lancado_por: SimpleUser | null;
  created_at: string;
  updated_at: string;
};

export type DespesaKpis = {
  total_despesas: number;
  valor_total: string;
  valor_pago: string;
  valor_pendente: string;
  pendentes_anexo: number;
};

export type RefinanciamentoItem = {
  id: number;
  contrato_id: number;
  contrato_codigo: string;
  associado_id: number;
  associado_nome: string;
  cpf_cnpj: string;
  matricula: string;
  matricula_display?: string;
  agente?: SimpleUser | null;
  solicitado_por?: SimpleUser | null;
  aprovado_por?: SimpleUser | null;
  bloqueado_por?: SimpleUser | null;
  efetivado_por?: SimpleUser | null;
  competencia_solicitada: string;
  status: string;
  valor_refinanciamento: string;
  repasse_agente: string;
  ciclo_key: string;
  referencias: string[];
  itens: Array<{
    id: number;
    numero: number;
    referencia_mes: string;
    valor: string;
    status: string;
  }>;
  mensalidades_pagas: number;
  mensalidades_total: number;
  refinanciamento_numero: number;
  pagamento_status: string;
  legacy_refinanciamento_id?: number | null;
  origem: string;
  data_renovacao: string | null;
  origem_renovacao: string;
  data_primeiro_ciclo_ativado: string | null;
  data_ativacao_ciclo: string | null;
  origem_data_ativacao: string;
  data_solicitacao_renovacao: string | null;
  ativacao_inferida: boolean;
  etapa_operacional: string;
  motivo_apto_renovacao: string;
  motivo_bloqueio?: string;
  observacao?: string;
  executado_em?: string | null;
  created_at: string;
  updated_at: string;
  auditoria: {
    solicitado_por?: SimpleUser | null;
    aprovado_por?: SimpleUser | null;
    bloqueado_por?: SimpleUser | null;
    efetivado_por?: SimpleUser | null;
    observacao?: string;
    motivo_bloqueio?: string;
  };
  comprovantes: ComprovanteResumo[];
};

export type RefinanciamentoResumo = {
  total: number;
  em_analise: number;
  assumidos: number;
  aprovados: number;
  efetivados: number;
  concluidos: number;
  bloqueados: number;
  revertidos: number;
  em_fluxo: number;
  com_anexo_agente: number;
  repasse_total: string;
};

export type PagamentoAgenteItem = {
  id: number;
  associado_id: number;
  nome: string;
  cpf_cnpj: string;
  contrato_codigo: string;
  status_contrato: string;
  status_visual_slug: string;
  status_visual_label: string;
  possui_meses_nao_descontados: boolean;
  meses_nao_descontados_count: number;
  data_contrato: string;
  auxilio_liberado_em: string | null;
  pagamento_inicial_status: string;
  pagamento_inicial_status_label: string;
  pagamento_inicial_valor: string | null;
  pagamento_inicial_paid_at: string | null;
  valor_mensalidade: string;
  comissao_agente: string;
  parcelas_total: number;
  parcelas_pagas: number;
  comprovantes_efetivacao: PagamentoInicialEvidencia[];
  pagamento_inicial_evidencias: PagamentoInicialEvidencia[];
  ciclos: Array<{
    id: number;
    numero: number;
    data_inicio: string;
    data_fim: string;
    status: string;
    status_visual_slug: string;
    status_visual_label: string;
    valor_total: string;
    parcelas: Array<{
      id: number;
      numero: number;
      referencia_mes: string;
      valor: string;
      data_vencimento: string;
      status: string;
      data_pagamento: string | null;
      observacao: string;
      comprovantes: Array<{
        id: string;
        nome: string;
        url: string;
        arquivo_referencia: string;
        arquivo_disponivel_localmente: boolean;
        tipo_referencia: string;
        origem: string;
        papel: string;
        tipo: string;
        status: string;
        competencia: string | null;
        created_at: string | null;
      }>;
    }>;
  }>;
};

export type PagamentoAgenteResumo = {
  total: number;
  efetivados: number;
  com_anexos: number;
  parcelas_pagas: number;
  parcelas_total: number;
};

export type PagamentoAgenteNotificacoes = {
  unread_count: number;
};

export type PaginatedPagamentosAgenteResponse =
  PaginatedResponse<PagamentoAgenteItem> & {
    resumo?: PagamentoAgenteResumo;
  };

export type ImportacaoResumo = {
  id: number;
  arquivo_nome: string;
  competencia: string;
  status: string;
  processado_em: string | null;
};

export type RelatorioResumo = {
  associados_ativos: number;
  associados_em_analise: number;
  associados_inadimplentes: number;
  contratos_ativos: number;
  contratos_em_analise: number;
  pendencias_abertas: number;
  esteira_aguardando: number;
  refinanciamentos_pendentes: number;
  refinanciamentos_efetivados: number;
  importacoes_concluidas: number;
  baixas_mes: number;
  valor_baixado_mes: string;
  ultima_importacao: ImportacaoResumo | null;
};

export type RelatorioGeradoItem = {
  id: number;
  nome: string;
  formato: string;
  created_at: string;
  download_url: string;
};
