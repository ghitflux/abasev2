import { get } from './client';
import { ENDPOINTS } from './constants';

export type DocKey =
  | 'doc_front' | 'doc_back' | 'comprovante_endereco'
  | 'contracheque_atual' | 'simulacao' | 'termo_adesao' | 'termo_antecipacao';

export type IssueStatus = 'open' | 'waiting_user' | 'received' | 'accepted' | 'rejected' | 'closed';

export type DocIssue = {
  id: number;
  associadodois_cadastro_id?: number;
  cpf_cnpj?: string;
  contrato_codigo_contrato?: string | null;
  title: string;
  message?: string | null;
  required_docs?: DocKey[] | null;
  status: IssueStatus | string;
  opened_at?: string | null;
  closed_at?: string | null;
  extras?: any;
  created_at?: string;
  updated_at?: string;
};

export type IssuesResponse = {
  issues: DocIssue[];
  cadastro?: { id: number; cpf_cnpj: string; contrato_codigo_contrato?: string | null } | null;
};

export async function fetchPendencias(): Promise<IssuesResponse> {
  const raw = await get<any>(ENDPOINTS.a2IssuesMy);
  return {
    issues: Array.isArray(raw?.issues) ? raw.issues : [],
    cadastro: raw?.cadastro ?? null,
  };
}
