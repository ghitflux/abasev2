// Endpoints da API ABASE
// Variável de ambiente: EXPO_PUBLIC_API_BASE_URL

export const BASE_URL = (
  process.env.EXPO_PUBLIC_API_BASE_URL ?? 'https://abasepiaui.cloud/api/v1'
).replace(/\/+$/, '');

export const ENDPOINTS = {
  // Auth
  authLogin: `${BASE_URL}/auth/login/`,
  authRefresh: `${BASE_URL}/auth/refresh/`,
  authLogout: `${BASE_URL}/auth/logout/`,
  authMe: `${BASE_URL}/auth/me/`,
  register: `${BASE_URL}/auth/register/`,
  forgotPassword: `${BASE_URL}/auth/forgot-password/`,
  resetPassword: `${BASE_URL}/auth/reset-password/`,

  // App self-service
  appMe: `${BASE_URL}/app/me/`,
  appMensalidades: `${BASE_URL}/app/mensalidades/`,
  appAntecipacao: `${BASE_URL}/app/antecipacao/`,
  appPendencias: `${BASE_URL}/app/pendencias/`,
  appDocumentos: `${BASE_URL}/app/documentos/`,
  appCadastro: `${BASE_URL}/app/cadastro/`,
  appCadastroCheckCpf: `${BASE_URL}/app/cadastro/check-cpf/`,
  appPendenciasReuploads: `${BASE_URL}/app/pendencias/reuploads/`,
  appTermosAceite: `${BASE_URL}/app/termos/aceite/`,
  appContato: `${BASE_URL}/app/contato/`,
  appAuxilio2Status: `${BASE_URL}/app/auxilio2/status/`,
  appAuxilio2Resumo: `${BASE_URL}/app/auxilio2/resumo/`,
  appAuxilio2Charge: `${BASE_URL}/app/auxilio2/charge/`,

  // WhatsApp (suporte)
  whatsappGeral:    'https://wa.me/5586981543302',
  whatsappJuridico: 'https://wa.me/5586988763302',
};
