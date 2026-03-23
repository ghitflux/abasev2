import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import {
  ActivityIndicator, Alert, Image, Linking, ScrollView,
  StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { useRouter } from 'expo-router';
import { useFocusEffect } from '@react-navigation/native';
import * as SecureStore from 'expo-secure-store';
import { useAuth } from '@/context/AuthContext';
import {
  createAuxilioDoisCharge, getAuxilioDoisStatus, getAuxilioDoisResumo,
  waitUntilPaid, type AuxilioDoisResumo,
} from '@/services/api/auxilioDoisService';
import { getEsperaResumo, type EsperaResumo } from '@/services/api/esperaService';
import { aceitarTermos, solicitarContato } from '@/services/api/cadastroService';

const BG = '#0f172a';
const CARD = '#0b1220';
const INK = '#e5e7eb';
const MUTED = '#94a3b8';
const BORDER = 'rgba(148,163,184,0.25)';
const BRAND = '#22d3ee';

const CONTACT_FLAG_KEY_PREFIX = 'espera:contact:submitted';

function moneyBR(v?: number | null) {
  if (v == null || Number.isNaN(Number(v))) return '—';
  try {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(v));
  } catch {
    const n = Number(v).toFixed(2).replace('.', ',');
    return `R$ ${n}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }
}

function toNumber(v: any): number {
  if (v == null) return 0;
  if (typeof v === 'number') return Number.isFinite(v) ? v : 0;
  const n = Number(String(v).replace(',', '.'));
  return Number.isFinite(n) ? n : 0;
}

export default function AuxilioEmergencialScreen() {
  const router = useRouter();
  const { token, user } = useAuth();

  const [booting, setBooting] = useState(true);
  const [working, setWorking] = useState(false);
  const [statusTxt, setStatusTxt] = useState<string>('—');
  const [valor, setValor] = useState<number | null>(null);
  const [pixCopiaECola, setPixCopiaECola] = useState<string | null>(null);
  const [imagemQrcode, setImagemQrcode] = useState<string | null>(null);
  const [espera, setEspera] = useState<EsperaResumo | null>(null);
  const [contactRequested, setContactRequested] = useState(false);
  const [contactSubmitting, setContactSubmitting] = useState(false);
  const pollAbortRef = useRef<{ aborted: boolean }>({ aborted: false });

  const firstName = useMemo(() => {
    const full = (user?.name || '').trim();
    return full ? full.split(/\s+/)[0] : 'Associado';
  }, [user]);

  const contactKey = useMemo(
    () => `${CONTACT_FLAG_KEY_PREFIX}:${user?.id ?? 'anon'}`,
    [user?.id],
  );

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      (async () => {
        try {
          const old = await SecureStore.getItemAsync(CONTACT_FLAG_KEY_PREFIX);
          if (old === '1') await SecureStore.deleteItemAsync(CONTACT_FLAG_KEY_PREFIX).catch(() => {});
          const v = await SecureStore.getItemAsync(contactKey);
          if (alive) setContactRequested(v === '1');
        } catch {}
      })();
      return () => { alive = false; };
    }, [contactKey]),
  );

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        if (!token) throw new Error('Sessão expirada');
        const [st, rs] = await Promise.all([
          getAuxilioDoisStatus().catch(() => null),
          getEsperaResumo().catch(() => null),
        ]);
        if (!alive) return;
        if (st) {
          setStatusTxt(String((st as any)?.status || '—'));
          setValor(toNumber((st as any)?.valor));
          setPixCopiaECola((st as any)?.pix_copia_cola ?? null);
          setImagemQrcode((st as any)?.imagem_qrcode ?? null);
        }
        if (rs) setEspera(rs);
      } catch {} finally {
        if (alive) setBooting(false);
      }
    })();
    return () => { alive = false; };
  }, [token]);

  useEffect(() => {
    return () => { pollAbortRef.current.aborted = true; };
  }, []);

  function openUrl(u?: string | null) {
    if (!u) return;
    Linking.openURL(u).catch(() => Alert.alert('Aviso', 'Não foi possível abrir o arquivo.'));
  }

  const canAccept = !!espera && !espera.aceiteTermos && !!(espera?.termos?.adesaoUrl || espera?.termos?.antecipacaoUrl);

  async function onAceitar() {
    try {
      await aceitarTermos();
      setEspera((prev) => prev ? ({ ...prev, aceiteTermos: true }) : prev);
      Alert.alert('Pronto', 'Seu aceite foi registrado.');
    } catch (e: any) {
      Alert.alert('Erro', e?.message || 'Falha ao registrar aceite.');
    }
  }

  async function onContato() {
    if (contactRequested || contactSubmitting) return;
    try {
      setContactSubmitting(true);
      await solicitarContato();
      await SecureStore.setItemAsync(contactKey, '1').catch(() => {});
      setContactRequested(true);
      Alert.alert('Contato', 'Recebemos seu pedido. Nossa equipe falará com você.');
    } catch (e: any) {
      Alert.alert('Erro', e?.message || 'Não foi possível registrar seu pedido.');
    } finally {
      setContactSubmitting(false);
    }
  }

  async function onGerarQr() {
    if (!token) { Alert.alert('Sessão', 'Sua sessão expirou. Faça login novamente.'); return; }
    setWorking(true);
    pollAbortRef.current.aborted = true;
    try {
      const r: AuxilioDoisResumo = await createAuxilioDoisCharge();
      setValor(toNumber(r?.valor));
      setPixCopiaECola(r?.pix_copia_cola ?? null);
      setImagemQrcode(r?.imagem_qrcode ?? null);
      setStatusTxt(String(r?.status || 'pendente'));

      pollAbortRef.current.aborted = false;
      startPolling();
    } catch (e: any) {
      Alert.alert('Erro', e?.message || 'Falha ao gerar a cobrança.');
    } finally {
      setWorking(false);
    }
  }

  function startPolling() {
    (async () => {
      try {
        const r = await waitUntilPaid(30, 3500);
        if (pollAbortRef.current.aborted || !r) return;
        setStatusTxt(String(r?.status || '—'));
        setValor(toNumber(r?.valor));
        setPixCopiaECola(r?.pix_copia_cola ?? null);
        setImagemQrcode(r?.imagem_qrcode ?? null);
        if (String(r?.status || '').toLowerCase() === 'pago') {
          await SecureStore.setItemAsync('auxilio2:forceEsperaOnce', '1').catch(() => {});
          Alert.alert('Pagamento confirmado', 'Sua filiação foi confirmada com sucesso!');
        }
      } catch {}
    })();
  }

  async function onVerificarPagamento() {
    try {
      const r = await getAuxilioDoisResumo();
      setStatusTxt(String(r?.status || '—'));
      setValor(toNumber(r?.valor));
      setPixCopiaECola(r?.pix_copia_cola ?? null);
      setImagemQrcode(r?.imagem_qrcode ?? null);
    } catch (e: any) {
      Alert.alert('Erro', e?.message || 'Falha ao consultar o status.');
    }
  }

  const gerarLbl = working ? 'Gerando…' : `Gerar QR Code${valor != null ? ` (${moneyBR(valor)})` : ''}`;
  const mensalidade = espera?.dados?.mensalidade ?? valor ?? null;
  const contactDisabled = booting || contactRequested || contactSubmitting;

  return (
    <View style={s.screen}>
      <ScrollView contentContainerStyle={{ padding: 18 }}>
        <View style={s.panel}>
          <Text style={s.brand}>ABASE</Text>
          <Text style={s.title}>Status do Cadastro</Text>

          <View style={s.card}>
            <Text style={s.cardTitle}>{`Olá${firstName ? `, ${firstName}` : ''}!`}</Text>
            <Text style={s.statusRow}>
              {'Status atual: '}
              <Text style={[s.badgeInline, { borderColor: BRAND, color: BRAND }]}>
                {booting ? '—' : (statusTxt || '—')}
              </Text>
            </Text>
            <Text style={s.muted}>Seu cadastro foi enviado e permanecerá nesta tela até a conclusão da análise.</Text>
          </View>

          <View style={s.card}>
            <Text style={s.cardTitle}>Condições definidas</Text>
            <View style={s.rowItem}>
              <Text style={s.label}>Mensalidade do Auxílio</Text>
              <Text style={s.value}>{moneyBR(mensalidade)}</Text>
            </View>
          </View>

          <TouchableOpacity
            style={[s.btnPrimary, { marginTop: 12, opacity: contactDisabled ? 0.55 : 1 }]}
            onPress={onContato}
            disabled={contactDisabled}
          >
            <Text style={s.btnPrimaryTxt}>Estou de acordo entre em contato comigo</Text>
          </TouchableOpacity>

          <View style={s.card}>
            <Text style={s.cardTitle}>Termos do contrato</Text>
            <View style={s.rowItem}>
              <View style={{ flex: 1 }}>
                <Text style={s.label}>Termo de Adesão</Text>
                <Text style={[s.muted, { marginTop: 2 }]}>
                  {espera?.termos?.adesaoUrl ? (espera?.termos?.adesaoUserUploaded ? 'Reenviado pelo associado' : 'Disponível para download') : 'Aguardando reenvio'}
                </Text>
              </View>
              <TouchableOpacity
                style={[s.btnMini, { opacity: espera?.termos?.adesaoUrl ? 1 : 0.5 }]}
                disabled={!espera?.termos?.adesaoUrl}
                onPress={() => openUrl(espera?.termos?.adesaoUrl)}
              >
                <Text style={s.btnMiniTxt}>Baixar</Text>
              </TouchableOpacity>
            </View>
            <View style={s.rowItem}>
              <View style={{ flex: 1 }}>
                <Text style={s.label}>Termo de Antecipação</Text>
                <Text style={[s.muted, { marginTop: 2 }]}>
                  {espera?.termos?.antecipacaoUrl ? (espera?.termos?.antecipacaoUserUploaded ? 'Reenviado pelo associado' : 'Disponível para download') : 'Aguardando reenvio'}
                </Text>
              </View>
              <TouchableOpacity
                style={[s.btnMini, { opacity: espera?.termos?.antecipacaoUrl ? 1 : 0.5 }]}
                disabled={!espera?.termos?.antecipacaoUrl}
                onPress={() => openUrl(espera?.termos?.antecipacaoUrl)}
              >
                <Text style={s.btnMiniTxt}>Baixar</Text>
              </TouchableOpacity>
            </View>
            <TouchableOpacity
              style={[s.btnAgree, { opacity: canAccept ? 1 : 0.5 }]}
              onPress={onAceitar}
              disabled={!canAccept}
            >
              <Text style={s.btnAgreeTxt}>{espera?.aceiteTermos ? 'Aceito' : 'Aceitar termos'}</Text>
            </TouchableOpacity>
          </View>

          <View style={s.card}>
            <Text style={s.cardTitle}>Pagamento do Auxílio</Text>
            <Text style={s.muted}>Após a sua análise, clique no botão abaixo e você receberá o valor integral do seu auxílio.</Text>
          </View>

          {!booting && (imagemQrcode || pixCopiaECola) && (
            <View style={[s.card, { marginTop: 12 }]}>
              <Text style={s.cardTitle}>Pagamento</Text>
              {!!imagemQrcode && (
                <View style={{ alignItems: 'center', marginTop: 10 }}>
                  <Image source={{ uri: imagemQrcode }} style={{ width: 220, height: 220, borderRadius: 8 }} resizeMode="contain" />
                </View>
              )}
              {!!pixCopiaECola && (
                <>
                  <Text style={[s.label, { marginTop: 12 }]}>Pix Copia e Cola</Text>
                  <Text selectable style={[s.value, { fontWeight: '600' }]}>{pixCopiaECola}</Text>
                  <Text style={s.hint}>Toque e segure para copiar o código.</Text>
                </>
              )}
            </View>
          )}

          {!booting && (
            <>
              <TouchableOpacity onPress={onGerarQr} disabled={working} style={[s.btnPrimary, { marginTop: 14 }, working && { opacity: 0.6 }]}>
                <Text style={s.btnPrimaryTxt}>{gerarLbl}</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={onVerificarPagamento} style={[s.btnGhost, { marginTop: 10 }]}>
                <Text style={s.btnGhostTxt}>Verificar pagamento</Text>
              </TouchableOpacity>
            </>
          )}

          <TouchableOpacity onPress={() => router.back()} style={[s.btnGhost, { marginTop: 10 }]}>
            <Text style={s.btnGhostTxt}>Voltar</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: BG },
  panel: { backgroundColor: 'rgba(11,18,32,0.96)', borderRadius: 16, padding: 14, borderWidth: 1, borderColor: BORDER },
  brand: { color: BRAND, fontSize: 26, fontWeight: '900', letterSpacing: 6, textAlign: 'center' },
  title: { color: INK, fontSize: 18, fontWeight: '800', marginTop: 4, marginBottom: 10, textAlign: 'center', letterSpacing: 0.2 },
  card: { backgroundColor: CARD, borderWidth: 1, borderColor: BORDER, borderRadius: 12, padding: 12, marginTop: 12, elevation: 3 },
  cardTitle: { color: INK, fontWeight: '900', fontSize: 16, marginBottom: 6, letterSpacing: 0.2 },
  muted: { color: MUTED },
  statusRow: { color: MUTED, marginBottom: 6 },
  badgeInline: { borderWidth: 1, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999, fontWeight: '900', overflow: 'hidden', marginLeft: 6 },
  rowItem: { paddingVertical: 8, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  label: { color: MUTED, flex: 1 },
  value: { color: INK, fontWeight: '800', flex: 1, textAlign: 'right' },
  hint: { color: '#9ca3af', fontSize: 12, marginTop: 6 },
  btnPrimary: { backgroundColor: BRAND, borderRadius: 12, alignItems: 'center', paddingVertical: 14, elevation: 2 },
  btnPrimaryTxt: { color: '#06121f', fontSize: 16, fontWeight: '900', letterSpacing: 0.3 },
  btnGhost: { borderRadius: 12, paddingVertical: 12, alignItems: 'center', borderWidth: 1, borderColor: BORDER },
  btnGhostTxt: { color: '#cbd5e1', fontWeight: '800' },
  btnAgree: { marginTop: 12, backgroundColor: BRAND, borderRadius: 12, alignItems: 'center', paddingVertical: 14, opacity: 0.95, elevation: 2 },
  btnAgreeTxt: { color: '#00121a', fontSize: 16, fontWeight: '900', letterSpacing: 0.3 },
  btnMini: { paddingHorizontal: 12, paddingVertical: 8, backgroundColor: 'rgba(148,163,184,0.12)', borderWidth: 1, borderColor: BORDER, borderRadius: 10 },
  btnMiniTxt: { color: INK, fontWeight: '800' },
});
