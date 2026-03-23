// Endpoints da API ABASE
// Variável de ambiente: EXPO_PUBLIC_API_BASE_URL

export const BASE_URL = (
  process.env.EXPO_PUBLIC_API_BASE_URL ?? 'https://www.abasepiaui.com/api'
).replace(/\/+$/, '');

export const ENDPOINTS = {
  // Auth
  login:    `${BASE_URL}/login`,
  logout:   `${BASE_URL}/logout`,
  home:     `${BASE_URL}/home`,
  me:       `${BASE_URL}/me`,
  register: `${BASE_URL}/auth/register`,
  checkEmail: `${BASE_URL}/auth/check-email`,
  forgotPassword: `${BASE_URL}/auth/forgot-password`,
  resetPassword:  `${BASE_URL}/auth/reset-password`,

  // App / mensalidades / antecipação
  mensalidades:      `${BASE_URL}/app/mensalidades`,
  mensalidadesCiclo: `${BASE_URL}/app/mensalidades/ciclo`,
  antecipacaoHistorico: `${BASE_URL}/app/antecipacao/historico`,

  // AssociadoDois (compatibilidade legada — mesmo path no novo backend)
  a2Status:        `${BASE_URL}/associadodois/status`,
  a2Cadastro:      `${BASE_URL}/associadodois/cadastro`,
  a2CheckCpf:      `${BASE_URL}/associadodois/check-cpf`,
  a2IssuesMy:      `${BASE_URL}/associadodois/issues/my`,
  a2Reuploads:     `${BASE_URL}/associadodois/reuploads`,
  a2AtualizarBasico: `${BASE_URL}/associadodois/atualizar-basico`,
  a2AceiteTermos:  `${BASE_URL}/associadodois/aceite-termos`,
  a2Contato:       `${BASE_URL}/associadodois/contato`,
  a2Auxilio2Status: `${BASE_URL}/associadodois/auxilio2/status`,
  a2Auxilio2Resumo: `${BASE_URL}/associadodois/auxilio2/resumo`,
  a2Auxilio2Charge: `${BASE_URL}/associadodois/auxilio2/charge-30`,

  // Associado (legacy)
  associadoMe:         `${BASE_URL}/associado/me`,
  associadoA2Status:   `${BASE_URL}/associado/a2/status`,
  associadoTermoAdesao:`${BASE_URL}/associado/termo-adesao`,

  // Novos endpoints v1 (novo backend Django)
  v1Me:          `${BASE_URL}/v1/app/me/`,
  v1Mensalidades:`${BASE_URL}/v1/app/mensalidades/`,
  v1Antecipacao: `${BASE_URL}/v1/app/antecipacao/`,
  v1Pendencias:  `${BASE_URL}/v1/app/pendencias/`,
  v1Documentos:  `${BASE_URL}/v1/app/documentos/`,

  // WhatsApp (suporte)
  whatsappGeral:    'https://wa.me/5586981543302',
  whatsappJuridico: 'https://wa.me/5586988763302',
};
