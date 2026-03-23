import { get, post, postForm } from './client';
import { ENDPOINTS } from './constants';
import type { LocalFile } from '@/types';

// Tipos do payload de cadastro básico
export type AccountType = 'corrente' | 'poupanca' | '' | undefined;
export type MaritalStatus =
  | 'SOLTEIRO' | 'CASADO' | 'SEPARADO' | 'DIVORCIADO' | 'VIUVO' | 'UNIAO_ESTAVEL' | '';

export type CadastroAssociadoPayload = {
  docType: 'CPF' | 'CNPJ';
  cpfCnpj: string;
  fullName: string;
  birthDate: string;
  rg?: string;
  orgaoExpedidor?: string;
  maritalStatus?: MaritalStatus;
  profession?: string;
  orgaoPublico: string;
  matriculaOrgao: string;
  situacaoServidor?: string;
  cellphone: string;
  email: string;
  cep: string;
  logradouro: string;
  numero: string;
  complemento?: string;
  bairro: string;
  cidade: string;
  uf: string;
  banco?: string;
  agencia?: string;
  conta?: string;
  tipoConta?: AccountType;
  chavePix?: string;
  cargo?: string;
  files?: {
    cpf_frente?: LocalFile | null;
    cpf_verso?: LocalFile | null;
    comp_endereco?: LocalFile | null;
    contracheque_atual?: LocalFile | null;
    termo_adesao?: LocalFile | null;
  };
};

function buildFormData(payload: CadastroAssociadoPayload): FormData {
  const fd = new FormData();

  const textFields: Record<string, string | undefined> = {
    doc_type: payload.docType,
    cpf_cnpj: payload.cpfCnpj,
    full_name: payload.fullName,
    birth_date: payload.birthDate,
    rg: payload.rg,
    orgao_expedidor: payload.orgaoExpedidor,
    estado_civil: payload.maritalStatus,
    profissao: payload.profession,
    orgao_publico: payload.orgaoPublico,
    matricula_orgao: payload.matriculaOrgao,
    situacao_servidor: payload.situacaoServidor,
    cellphone: payload.cellphone,
    email: payload.email,
    cep: payload.cep,
    logradouro: payload.logradouro,
    numero: payload.numero,
    complemento: payload.complemento,
    bairro: payload.bairro,
    cidade: payload.cidade,
    uf: payload.uf,
    banco: payload.banco,
    agencia: payload.agencia,
    conta: payload.conta,
    tipo_conta: payload.tipoConta,
    chave_pix: payload.chavePix,
    cargo: payload.cargo,
  };

  Object.entries(textFields).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') {
      fd.append(k, v);
    }
  });

  if (payload.files) {
    Object.entries(payload.files).forEach(([key, file]) => {
      if (file) {
        fd.append(key, { uri: file.uri, name: file.name, type: file.type } as any);
      }
    });
  }

  return fd;
}

export async function submitCadastroAssociadoBasico(
  payload: CadastroAssociadoPayload,
): Promise<any> {
  const fd = buildFormData(payload);
  return postForm<any>(ENDPOINTS.appCadastro, fd);
}

export async function checkCpfDuplicadoBasico(cpf: string): Promise<{ exists: boolean }> {
  return get<{ exists: boolean }>(ENDPOINTS.appCadastroCheckCpf, { cpf });
}

export async function getCadastroStatus(): Promise<any> {
  return get<any>(ENDPOINTS.appCadastro);
}

export async function getCadastroShowMy(): Promise<any> {
  return get<any>(ENDPOINTS.appCadastro);
}

export async function getAssociadoDoisCadastro(): Promise<any> {
  return get<any>(ENDPOINTS.appCadastro);
}

export async function getIssuesMy(): Promise<any> {
  return get<any>(ENDPOINTS.appPendencias);
}

export async function submitReuploadBasico(files: Record<string, LocalFile>): Promise<any> {
  const fd = new FormData();
  Object.entries(files).forEach(([key, file]) => {
    if (file) {
      fd.append(key, { uri: file.uri, name: file.name, type: file.type } as any);
    }
  });
  return postForm<any>(ENDPOINTS.appPendenciasReuploads, fd);
}

export async function aceitarTermos(): Promise<any> {
  return post<any>(ENDPOINTS.appTermosAceite, {});
}

export async function solicitarContato(mensagem?: string): Promise<any> {
  return post<any>(ENDPOINTS.appContato, { mensagem: mensagem ?? '' });
}
