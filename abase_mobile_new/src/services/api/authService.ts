import { get, post, setApiAccessToken } from './client';
import { ENDPOINTS } from './constants';
import { clearStoredTokens, getStoredRefreshToken, persistTokens } from './session';
import type {
  LoginResponse,
  HomeResponse,
  MeResponse,
  RegisterParams,
  RegisterResponse,
  AuthPayload,
  Bootstrap,
  PerfilData,
  Roles,
} from '@/types';
import {
  onlyDigits,
  looksLikeEmail,
  maskDocHideMiddle,
  formatPhoneBR,
} from '@/utils/format';
export type { PerfilData } from '@/types';

function normalizeBootstrap(payload: HomeResponse | null | undefined): Bootstrap {
  return {
    pessoa: payload?.pessoa ?? {
      nome_razao_social: '',
      documento: '',
      email: '',
      celular: '',
      orgao_publico: '',
      cidade: '',
      uf: '',
    },
    vinculo_publico: payload?.vinculo_publico ?? {
      orgao_publico: '',
      situacao_servidor: '',
      matricula: '',
    },
    dados_bancarios: payload?.dados_bancarios ?? {
      banco: '',
      agencia: '',
      conta: '',
      tipo_conta: '',
      chave_pix: '',
    },
    contratos: payload?.contratos || [],
    resumo: payload?.resumo ?? {
      prazo: 0,
      parcela_valor: 0,
      total_financiado: 0,
      status_contrato: 'Sem contrato',
      parcelas_pagas: 0,
      parcelas_restantes: 0,
      atraso: 0,
      abertas_total: 0,
      total_pago: 0,
      restante: 0,
      percentual_pago: 0,
      elegivel_antecipacao: false,
      mensalidade: 0,
    },
    proximaRef: (payload as any)?.proximaRef ?? null,
    termo_adesao: payload?.termo_adesao ?? null,
    aceite_termos: payload?.aceite_termos,
    cadastro: payload?.cadastro,
    whatsapps: payload?.whatsapps,
    issues: payload?.issues,
    pendencias: payload?.pendencias,
    permissions: payload?.permissions,
    auxilios: payload?.auxilios,
    termos: payload?.termos,
    exists: payload?.exists,
    status: payload?.status,
    basic_complete: payload?.basic_complete,
    complete: payload?.complete,
  };
}

async function fetchBootstrap(): Promise<HomeResponse> {
  return get<HomeResponse>(ENDPOINTS.appMe);
}

function resolveRoles(home: HomeResponse | null | undefined, login: LoginResponse): Roles {
  const fromHome = home?.roles;
  if (Array.isArray(fromHome) && fromHome.length > 0) return fromHome;
  if (Array.isArray(login.roles) && login.roles.length > 0) return login.roles;
  const fromUser = (login.user as any)?.roles;
  return Array.isArray(fromUser) ? fromUser : [];
}

export async function loginApi(params: {
  login: string;
  password: string;
}): Promise<AuthPayload> {
  const rawLogin = (params.login ?? '').trim();
  const isEmail = looksLikeEmail(rawLogin);

  const payload = {
    login: isEmail ? rawLogin : onlyDigits(rawLogin),
    password: isEmail ? (params.password ?? '') : onlyDigits(params.password ?? ''),
  };

  const r = await post<LoginResponse>(ENDPOINTS.authLogin, payload);
  await persistTokens(r.access, r.refresh);
  setApiAccessToken(r.access);

  try {
    const home = await fetchBootstrap();
    return {
      token: r.access,
      refreshToken: r.refresh,
      user: home?.user ?? r.user,
      roles: resolveRoles(home, r),
      bootstrap: normalizeBootstrap(home),
    };
  } catch (error) {
    setApiAccessToken(null);
    await clearStoredTokens();
    throw error;
  }
}

export async function logoutApi(): Promise<void> {
  try {
    const refreshToken = await getStoredRefreshToken();
    if (!refreshToken) return;
    await post(ENDPOINTS.authLogout, { refresh: refreshToken });
  } catch {
    // idempotente
  }
}

export async function fetchHome(): Promise<Bootstrap> {
  const response = await fetchBootstrap();
  return normalizeBootstrap(response);
}

export async function fetchMe(): Promise<MeResponse> {
  return get<MeResponse>(ENDPOINTS.appMe);
}

export async function registerApi(params: RegisterParams): Promise<RegisterResponse> {
  const response = await post<any>(ENDPOINTS.register, params);
  return {
    ok: Boolean(response?.ok ?? true),
    message: response?.message,
    token: response?.access,
    refreshToken: response?.refresh ?? null,
    user: response?.user,
    roles: response?.roles ?? response?.user?.roles ?? [],
  };
}

export async function forgotPasswordApi(email: string): Promise<{ ok: boolean; message?: string }> {
  return post(ENDPOINTS.forgotPassword, { email });
}

export async function resetPasswordApi(params: {
  token: string;
  password: string;
  password_confirmation: string;
  email?: string;
}): Promise<{ ok: boolean; message?: string }> {
  return post(ENDPOINTS.resetPassword, params);
}

export async function getPerfilData(): Promise<PerfilData> {
  const home = await fetchHome();

  const fullName = home?.pessoa?.nome_razao_social || 'Associado';
  const email = home?.pessoa?.email || '';
  const phoneRaw = home?.pessoa?.celular || undefined;
  const phone = phoneRaw ? formatPhoneBR(phoneRaw) : undefined;
  const doc = onlyDigits(home?.pessoa?.documento) || undefined;

  const pagas = Number(home?.resumo?.parcelas_pagas ?? 0);
  const prazo = Number(home?.resumo?.prazo ?? 0);

  const rawStatus = String(home?.resumo?.status_contrato || '').toLowerCase();
  let statusLabel = 'Mensalidades à vencer';
  if (rawStatus.includes('conclu')) statusLabel = 'Concluído';
  else if (rawStatus.includes('atras') || rawStatus.includes('inadimpl')) {
    statusLabel = 'Em atraso';
  }

  const termoUrl =
    home?.termo_adesao?.url ||
    home?.termos?.adesao_admin_url ||
    home?.termos?.adesaoUrl ||
    null;
  const termoName = home?.termo_adesao?.name || 'ADES.pdf';

  return {
    fullName,
    email,
    phone,
    cpf: doc,
    cpfMasked: doc ? maskDocHideMiddle(doc) : undefined,
    descontadas: pagas,
    total: prazo,
    statusLabel,
    termo: termoUrl ? { name: termoName, url: termoUrl } : null,
  };
}
