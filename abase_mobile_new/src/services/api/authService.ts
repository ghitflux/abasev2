import { get, post } from './client';
import { ENDPOINTS, BASE_URL } from './constants';
import type {
  LoginResponse,
  HomeResponse,
  MeResponse,
  RegisterParams,
  RegisterResponse,
  AuthPayload,
  Bootstrap,
  PerfilData,
} from '@/types';
import {
  onlyDigits,
  looksLikeEmail,
  maskDocHideMiddle,
  formatPhoneBR,
} from '@/utils/format';

function withTokenQuery(url: string, token: string) {
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}token=${encodeURIComponent(token)}`;
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

  const r = await post<LoginResponse>(ENDPOINTS.login, payload);

  return {
    token: r.token,
    user: r.user,
    roles: r.roles ?? [],
    bootstrap: {
      pessoa: r.pessoa,
      vinculo_publico: r.vinculo_publico,
      dados_bancarios: r.dados_bancarios,
      contratos: r.contratos || [],
      resumo: r.resumo,
      termo_adesao: r.termo_adesao ?? null,
      aceite_termos: r.aceite_termos,
      cadastro: r.cadastro,
      whatsapps: r.whatsapps,
    },
  };
}

export async function logoutApi(): Promise<void> {
  try {
    await post<{ ok: boolean }>(ENDPOINTS.logout);
  } catch {
    // idempotente
  }
}

export async function fetchHome(): Promise<Bootstrap> {
  const r = await get<HomeResponse>(ENDPOINTS.home);
  return {
    pessoa: r.pessoa,
    vinculo_publico: r.vinculo_publico,
    dados_bancarios: r.dados_bancarios,
    contratos: r.contratos || [],
    resumo: r.resumo,
    termo_adesao: r.termo_adesao ?? null,
    aceite_termos: r.aceite_termos,
    cadastro: r.cadastro,
    whatsapps: r.whatsapps,
  };
}

export async function fetchMe(): Promise<MeResponse> {
  return get<MeResponse>(ENDPOINTS.me);
}

export async function registerApi(params: RegisterParams): Promise<RegisterResponse> {
  return post<RegisterResponse>(ENDPOINTS.register, params);
}

export async function forgotPasswordApi(email: string): Promise<{ ok: boolean; message?: string }> {
  return post(ENDPOINTS.forgotPassword, { email });
}

export async function resetPasswordApi(params: {
  token: string;
  password: string;
  password_confirmation: string;
}): Promise<{ ok: boolean; message?: string }> {
  return post(ENDPOINTS.resetPassword, params);
}

export async function getPerfilData(): Promise<PerfilData> {
  const home = await fetchHome().catch(() => null as any);

  let pessoaFromAssoc: any = null;
  try {
    const assoc = await get<any>(ENDPOINTS.associadoMe);
    pessoaFromAssoc = assoc?.pessoa || null;
  } catch {
    pessoaFromAssoc = null;
  }

  let a2Cadastro: any = null;
  try {
    const cad = await get<any>(ENDPOINTS.a2Cadastro);
    a2Cadastro = cad?.cadastro ?? cad ?? null;
  } catch {
    a2Cadastro = null;
  }

  const fullName =
    pessoaFromAssoc?.nome_razao_social ||
    a2Cadastro?.full_name ||
    home?.pessoa?.nome_razao_social ||
    'Associado';

  const email =
    pessoaFromAssoc?.email ||
    a2Cadastro?.email ||
    home?.pessoa?.email ||
    '';

  const phoneRaw =
    a2Cadastro?.cellphone ||
    pessoaFromAssoc?.celular ||
    home?.pessoa?.celular ||
    undefined;

  const phone = phoneRaw ? formatPhoneBR(phoneRaw) : undefined;

  const doc =
    onlyDigits(a2Cadastro?.cpf_cnpj) ||
    onlyDigits(pessoaFromAssoc?.documento) ||
    onlyDigits(home?.pessoa?.documento) ||
    undefined;

  const pagas = Number(home?.resumo?.parcelas_pagas ?? 0);
  const prazo = Number(home?.resumo?.prazo ?? 0);

  const rawStatus = String(home?.resumo?.status_contrato || '').toLowerCase();
  let statusLabel = 'Mensalidades à vencer';
  if (rawStatus.includes('conclu')) statusLabel = 'Concluído';
  else if (rawStatus.includes('atras') || rawStatus.includes('inadimpl'))
    statusLabel = 'Em atraso';

  const termoApiBase = `${BASE_URL}/associado/termo-adesao`;
  const termoApiUrl = withTokenQuery(termoApiBase, token);

  const homeHasTermo =
    !!home?.termo_adesao &&
    (typeof home?.termo_adesao?.relative_path === 'string' ||
      typeof home?.termo_adesao?.url === 'string');

  let termoUrl: string | null = homeHasTermo ? termoApiUrl : null;

  if (!termoUrl) {
    try {
      const a2s = await get<any>(ENDPOINTS.associadoA2Status);
      if (a2s?.termos?.adesao_admin_url || a2s?.termo_adesao || a2s?.termos?.adesao) {
        termoUrl = termoApiUrl;
      }
    } catch {
      try {
        const a2s2 = await get<any>(ENDPOINTS.a2Status);
        if (a2s2?.termos?.adesao_admin_url || a2s2?.termo_adesao || a2s2?.termos?.adesao) {
          termoUrl = termoApiUrl;
        }
      } catch {
        termoUrl = null;
      }
    }
  }

  const termoName =
    termoUrl
      ? (home?.termo_adesao?.name as string) || 'termo_adesao.pdf'
      : 'ADES.pdf';

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
