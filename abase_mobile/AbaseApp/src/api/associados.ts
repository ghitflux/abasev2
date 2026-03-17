import apiClient from './client';

export interface CadastroAssociadoPayload {
  nome_completo: string;
  cpf_cnpj: string;
  email: string;
  telefone: string;
  data_nascimento?: string;
  profissao?: string;
  cargo?: string;
  orgao_publico?: string;
  matricula_orgao?: string;
}

export async function criarAssociado(payload: CadastroAssociadoPayload): Promise<{ id: number }> {
  const { data } = await apiClient.post('/associados/', payload);
  return data;
}

export async function validarCpf(cpf: string): Promise<{ exists: boolean; message: string | null }> {
  const { data } = await apiClient.get('/associados/validar-documento/', {
    params: { cpf_cnpj: cpf.replace(/\D/g, '') },
  });
  return data;
}
