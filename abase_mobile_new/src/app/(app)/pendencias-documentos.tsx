import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert, Keyboard, KeyboardAvoidingView, Platform, Pressable,
  ScrollView, StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { useRouter } from 'expo-router';
import { useAuth } from '@/context/AuthContext';
import { fetchPendencias, type DocIssue, type DocKey, type IssueStatus } from '@/services/api/pendenciasService';

const BG = '#0f172a';
const BRAND = '#22d3ee';

const docLabels: Record<DocKey, string> = {
  doc_front: 'Documento (frente)',
  doc_back: 'Documento (verso)',
  comprovante_endereco: 'Comprovante de endereço',
  contracheque_atual: 'Contracheque atual',
  simulacao: 'Simulação',
  termo_adesao: 'Termo de Adesão',
  termo_antecipacao: 'Termo de Antecipação',
};

const REENVIAVEL: IssueStatus[] = ['open', 'waiting_user'];

export default function PendenciasDocumentosScreen() {
  const router = useRouter();
  const { token } = useAuth();

  const [loading, setLoading] = useState(true);
  const [issues, setIssues] = useState<DocIssue[]>([]);

  useEffect(() => {
    (async () => {
      if (!token) return;
      try {
        const res = await fetchPendencias();
        const arr = Array.isArray(res.issues) ? res.issues : [];
        const toTS = (x?: string | null) => (x ? Date.parse(x) || 0 : 0);
        const sorted = [...arr].sort((a, b) => {
          const aTS = Math.max(toTS(a.updated_at), toTS(a.created_at), toTS(a.opened_at), a.id || 0);
          const bTS = Math.max(toTS(b.updated_at), toTS(b.created_at), toTS(b.opened_at), b.id || 0);
          return bTS - aTS;
        });
        setIssues(sorted);
      } catch (e: any) {
        Alert.alert('Erro', e?.message || 'Não foi possível carregar suas pendências.');
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  const latestId = useMemo(() => (issues.length ? issues[0].id : null), [issues]);
  const canClick = (issue: DocIssue) => latestId === issue.id && REENVIAVEL.includes(issue.status);

  if (loading) {
    return (
      <View style={[s.screen, { alignItems: 'center', justifyContent: 'center' }]}>
        <Text style={{ color: '#cbd5e1' }}>Carregando pendências...</Text>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView style={s.screen} behavior={Platform.select({ ios: 'padding', android: 'height' })}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 18 }}>
        <Pressable onPress={Keyboard.dismiss}>
          <View style={s.panel}>
            <View style={s.headerWrap}>
              <Text style={s.brand}>ABASE</Text>
              <Text style={s.title}>Pendências de Documentos</Text>
              <Text style={s.subtitle}>
                Este é o checklist solicitado pela análise. Para reenviar documentos, você deve abrir o seu cadastro.
              </Text>
              <Text style={s.note}>
                Dica: apenas a <Text style={{ fontWeight: '800', color: '#e5e7eb' }}>pendência mais recente</Text> fica habilitada para reenvio.
              </Text>
            </View>

            {issues.length === 0 ? (
              <View style={{ padding: 12, backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 10 }}>
                <Text style={{ color: '#e5e7eb' }}>Não há pendências ativas no momento.</Text>
              </View>
            ) : (
              issues.map((issue) => {
                const enabled = canClick(issue);
                return (
                  <View key={issue.id} style={s.issueCard}>
                    <Text style={s.issueTitle}>{issue.title || 'Documentação pendente'}</Text>
                    {!!issue.message && <Text style={s.issueMsg}>{issue.message}</Text>}
                    <Text style={s.issueStatus}>
                      Status <Text style={s.issueStatusValue}>{issue.status}</Text>
                    </Text>
                    {Array.isArray(issue.required_docs) && issue.required_docs.length > 0 ? (
                      <View style={{ marginTop: 10 }}>
                        <Text style={s.docsTitle}>Documentos solicitados:</Text>
                        {issue.required_docs.map((slot: DocKey) => (
                          <Text key={slot} style={s.docItem}>• {docLabels[slot] || String(slot)}</Text>
                        ))}
                      </View>
                    ) : (
                      <Text style={s.noDocs}>
                        O analista não marcou documentos específicos. Verifique seu cadastro completo.
                      </Text>
                    )}
                    <TouchableOpacity
                      style={enabled ? s.btnPrimary : s.btnDisabled}
                      onPress={enabled ? () => router.push('/(app)/cadastro-associado') : undefined}
                      activeOpacity={enabled ? 0.7 : 1}
                      disabled={!enabled}
                    >
                      <Text style={enabled ? s.btnPrimaryTxt : s.btnDisabledTxt}>Abrir cadastro para reenviar</Text>
                    </TouchableOpacity>
                  </View>
                );
              })
            )}
          </View>
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: BG },
  panel: { backgroundColor: 'rgba(2,6,23,0.9)', borderRadius: 16, padding: 14 },
  headerWrap: { alignItems: 'center', marginBottom: 12 },
  brand: { color: BRAND, fontSize: 22, fontWeight: '900', letterSpacing: 4 },
  title: { color: '#e5e7eb', fontSize: 18, fontWeight: '700', marginTop: 4, marginBottom: 4 },
  subtitle: { color: '#94a3b8', fontSize: 13, textAlign: 'center' },
  note: { color: '#94a3b8', fontSize: 12, textAlign: 'center', marginTop: 8 },
  issueCard: { borderWidth: 1, borderColor: 'rgba(148,163,184,0.25)', borderRadius: 12, padding: 12, marginTop: 12 },
  issueTitle: { color: '#e5e7eb', fontWeight: '800', fontSize: 16 },
  issueMsg: { color: '#94a3b8', marginTop: 6 },
  issueStatus: { color: '#94a3b8', marginTop: 6 },
  issueStatusValue: { color: BRAND, fontWeight: '800' },
  docsTitle: { color: '#9ca3af', marginBottom: 4, fontWeight: '700' },
  docItem: { color: '#e5e7eb', fontSize: 13, marginBottom: 2 },
  noDocs: { color: '#9ca3af', marginTop: 8, fontStyle: 'italic' },
  btnPrimary: { marginTop: 10, backgroundColor: BRAND, borderRadius: 12, alignItems: 'center', paddingVertical: 12 },
  btnPrimaryTxt: { color: '#06121f', fontSize: 15, fontWeight: '900', letterSpacing: 0.3 },
  btnDisabled: { marginTop: 10, backgroundColor: '#263445', borderRadius: 12, alignItems: 'center', paddingVertical: 12, opacity: 0.7 },
  btnDisabledTxt: { color: '#94a3b8', fontSize: 15, fontWeight: '900', letterSpacing: 0.3 },
});
