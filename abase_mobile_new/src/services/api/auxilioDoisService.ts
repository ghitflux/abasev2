import { get, post } from './client';
import { ENDPOINTS } from './constants';

export type AuxilioDoisStatus = {
  status?: string;
  status_label?: string;
  valor?: number;
  allowed?: boolean;
  has_pending?: boolean;
  [key: string]: any;
};

export type AuxilioDoisResumo = {
  txid?: string;
  valor?: number;
  status?: string;
  pix_copia_cola?: string;
  imagem_qrcode?: string;
  created_at?: string;
  paid_at?: string | null;
  [key: string]: any;
};

export async function getAuxilioDoisStatus(): Promise<AuxilioDoisStatus> {
  return get<AuxilioDoisStatus>(ENDPOINTS.a2Auxilio2Status);
}

export async function getAuxilioDoisResumo(): Promise<AuxilioDoisResumo> {
  return get<AuxilioDoisResumo>(ENDPOINTS.a2Auxilio2Resumo);
}

export async function createAuxilioDoisCharge(): Promise<AuxilioDoisResumo> {
  return post<AuxilioDoisResumo>(ENDPOINTS.a2Auxilio2Charge, {});
}

/** Polling: aguarda status "pago" por até maxAttempts * intervalMs */
export async function waitUntilPaid(
  maxAttempts = 30,
  intervalMs = 5000,
): Promise<AuxilioDoisResumo | null> {
  for (let i = 0; i < maxAttempts; i++) {
    const resumo = await getAuxilioDoisResumo().catch(() => null);
    if (resumo && String(resumo.status || '').toLowerCase() === 'pago') return resumo;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  return null;
}
