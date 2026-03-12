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

export type Metrica = {
  count: number;
  variacao_percentual: number;
};

export type AssociadoMetricas = {
  total: Metrica;
  ativos: Metrica;
  em_analise: Metrica;
  inativos: Metrica;
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

export type Ciclo = {
  id: number;
  numero: number;
  data_inicio: string;
  data_fim: string;
  status: string;
  valor_total: string;
  parcelas: Parcela[];
};

export type Documento = {
  id: number;
  tipo: string;
  arquivo: string;
  status: string;
  observacao: string;
  created_at?: string;
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
  ciclos: Ciclo[];
};

export type AssociadoListItem = {
  id: number;
  nome_completo: string;
  matricula: string;
  cpf_cnpj: string;
  status: string;
  agente?: SimpleUser | null;
  ciclos_abertos: number;
  ciclos_fechados: number;
};

export type AssociadoDetail = {
  id: number;
  matricula: string;
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
  observacao?: string;
  agente?: SimpleUser | null;
  endereco?: Endereco | null;
  dados_bancarios?: DadosBancarios | null;
  contato?: Contato | null;
  contratos: ContratoResumo[];
  documentos: Documento[];
  esteira?: EsteiraResumo | null;
};

export type EsteiraContrato = {
  codigo: string;
  associado_nome: string;
  cpf_cnpj: string;
  matricula: string;
};

export type EsteiraItem = {
  id: number;
  ordem: number;
  contrato: EsteiraContrato | null;
  data_assinatura: string | null;
  valor_disponivel: string | null;
  comissao_agente: string | null;
  status_contrato: string | null;
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
  | "ativos"
  | "todos"
  | "recebidos"
  | "recebida"
  | "reenvio"
  | "incompleta"
  | "pendente";

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
  cpf_cnpj: string;
  contrato_codigo: string | null;
  created_at: string;
  resolvida_em: string | null;
};

export type ContratoListItem = {
  id: number;
  codigo: string;
  associado: {
    id: number;
    nome_completo: string;
    matricula: string;
    cpf_cnpj: string;
    orgao_publico: string;
    matricula_orgao: string;
  };
  agente?: SimpleUser | null;
  status: string;
  status_resumido: string;
  status_contrato_visual: string;
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
};

export type ContratoResumoCards = {
  total: number;
  concluidos: number;
  ativos: number;
  pendentes: number;
  inadimplentes: number;
};

export type ComprovanteResumo = {
  id: number;
  tipo: string;
  papel: string;
  arquivo: string;
  nome_original: string;
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

export type RefinanciamentoItem = {
  id: number;
  contrato_id: number;
  contrato_codigo: string;
  associado_id: number;
  associado_nome: string;
  cpf_cnpj: string;
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

export type PagamentoAgenteItem = {
  id: number;
  associado_id: number;
  nome: string;
  cpf_cnpj: string;
  contrato_codigo: string;
  status_contrato: string;
  data_contrato: string;
  auxilio_liberado_em: string | null;
  valor_mensalidade: string;
  comissao_agente: string;
  parcelas_total: number;
  parcelas_pagas: number;
  comprovantes_efetivacao: Array<{
    id: string;
    nome: string;
    url: string;
    origem: string;
    papel: string;
    tipo: string;
    status: string;
    competencia: string | null;
    created_at: string | null;
  }>;
  ciclos: Array<{
    id: number;
    numero: number;
    data_inicio: string;
    data_fim: string;
    status: string;
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
