import apiClient from './client';
import type {
  AntecipacaoResponse,
  HomeMeResponse,
  MensalidadesResponse,
  PendenciasResponse,
} from '../types';

export async function fetchMe(): Promise<HomeMeResponse> {
  const { data } = await apiClient.get<HomeMeResponse>('/app/me/');
  return data;
}

export async function fetchMensalidades(): Promise<MensalidadesResponse> {
  const { data } = await apiClient.get<MensalidadesResponse>('/app/mensalidades/');
  return data;
}

export async function fetchAntecipacao(): Promise<AntecipacaoResponse> {
  const { data } = await apiClient.get<AntecipacaoResponse>('/app/antecipacao/');
  return data;
}

export async function fetchPendencias(): Promise<PendenciasResponse> {
  const { data } = await apiClient.get<PendenciasResponse>('/app/pendencias/');
  return data;
}

export async function uploadDocumento(
  tipo: string,
  fileUri: string,
  fileName: string,
  mimeType: string,
  observacao?: string,
): Promise<void> {
  const formData = new FormData();
  formData.append('tipo', tipo);
  formData.append('arquivo', { uri: fileUri, name: fileName, type: mimeType } as unknown as Blob);
  if (observacao) {
    formData.append('observacao', observacao);
  }

  await apiClient.post('/app/documentos/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
}
