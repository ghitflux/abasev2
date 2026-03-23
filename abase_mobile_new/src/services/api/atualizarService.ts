import { get, postForm } from './client';
import { ENDPOINTS } from './constants';
import type { LocalFile } from '@/types';
import type { CadastroAssociadoPayload } from './cadastroService';

export async function getCadastroStatus(): Promise<any> {
  return get<any>(ENDPOINTS.appCadastro);
}

export async function submitAtualizarBasico(
  payload: CadastroAssociadoPayload,
): Promise<any> {
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
    if (v !== undefined && v !== null && v !== '') fd.append(k, v);
  });

  if (payload.files) {
    Object.entries(payload.files).forEach(([key, file]) => {
      if (file) {
        fd.append(key, { uri: file.uri, name: file.name, type: file.type } as any);
      }
    });
  }

  return postForm<any>(ENDPOINTS.appCadastro, fd);
}

export async function uploadDocumento(tipo: string, file: LocalFile, observacao?: string): Promise<any> {
  const fd = new FormData();
  fd.append('tipo', tipo);
  fd.append('arquivo', { uri: file.uri, name: file.name, type: file.type } as any);
  if (observacao) fd.append('observacao', observacao);
  return postForm<any>(ENDPOINTS.appDocumentos, fd);
}
