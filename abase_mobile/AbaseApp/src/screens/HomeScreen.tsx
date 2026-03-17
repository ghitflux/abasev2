import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';

import { fetchMe } from '../api/app';
import { useAuth } from '../context/AuthContext';
import type { HomeMeResponse } from '../types';
import { formatCurrency, formatDate, statusAssociadoLabel } from '../utils/formatters';

export default function HomeScreen() {
  const { user, logout, hasRole } = useAuth();
  const [data, setData] = useState<HomeMeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const isAssociado = hasRole('ASSOCIADO');

  const load = useCallback(async () => {
    if (!isAssociado) {
      setLoading(false);
      return;
    }
    try {
      const result = await fetchMe();
      setData(result);
    } catch {
      Alert.alert('Erro', 'Não foi possível carregar seus dados.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [isAssociado]);

  useEffect(() => {
    load();
  }, [load]);

  function onRefresh() {
    setRefreshing(true);
    load();
  }

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#1B4F9C" />
      </View>
    );
  }

  // Visão para Agente/Admin
  if (!isAssociado) {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Olá, {user?.first_name || 'Agente'}</Text>
          <TouchableOpacity onPress={logout}>
            <Text style={styles.logoutText}>Sair</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.centered}>
          <Text style={styles.emptyText}>Use as abas para gerenciar associados.</Text>
        </View>
      </View>
    );
  }

  const associado = data?.associado;
  const resumo = data?.resumo;
  const contratos = data?.contratos ?? [];
  const pendencias = data?.pendencias ?? [];

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>Olá, {associado?.nome_completo?.split(' ')[0]}</Text>
          <Text style={styles.headerSub}>{statusAssociadoLabel(associado?.status ?? '')}</Text>
        </View>
        <TouchableOpacity onPress={logout}>
          <Text style={styles.logoutText}>Sair</Text>
        </TouchableOpacity>
      </View>

      {/* Resumo financeiro */}
      {resumo && (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Resumo Financeiro</Text>
          <View style={styles.row}>
            <Stat label="Parcelas pagas" value={`${resumo.parcelas_pagas}/${resumo.parcelas_total}`} />
            <Stat label="Mensalidade" value={formatCurrency(resumo.valor_mensalidade)} />
          </View>
          <View style={styles.row}>
            <Stat
              label="Próx. vencimento"
              value={resumo.proximo_vencimento ? formatDate(resumo.proximo_vencimento) : '—'}
            />
            <Stat
              label="Em atraso"
              value={String(resumo.em_atraso)}
              accent={resumo.em_atraso > 0}
            />
          </View>
        </View>
      )}

      {/* Contratos */}
      {contratos.length > 0 && (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Contratos</Text>
          {contratos.map((c) => (
            <View key={c.id} style={styles.contratoRow}>
              <Text style={styles.contratoCode}>{c.codigo}</Text>
              <Text style={styles.contratoDetail}>
                {formatCurrency(c.valor_mensalidade)} · {c.prazo_meses} meses · {c.status}
              </Text>
              {c.data_primeira_mensalidade && (
                <Text style={styles.contratoDetail}>
                  Início: {formatDate(c.data_primeira_mensalidade)}
                </Text>
              )}
            </View>
          ))}
        </View>
      )}

      {/* Pendências */}
      {pendencias.length > 0 && (
        <View style={[styles.card, styles.cardAlert]}>
          <Text style={styles.cardTitle}>⚠️ Pendências ({pendencias.length})</Text>
          {pendencias.map((p) => (
            <View key={p.id} style={styles.pendenciaRow}>
              <Text style={styles.pendenciaTipo}>{p.tipo}</Text>
              <Text style={styles.pendenciaDesc}>{p.descricao}</Text>
            </View>
          ))}
        </View>
      )}

      <View style={{ height: 24 }} />
    </ScrollView>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={[styles.statValue, accent && styles.statValueAccent]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F0F4FA' },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  header: {
    backgroundColor: '#1B4F9C',
    paddingTop: 56,
    paddingBottom: 20,
    paddingHorizontal: 20,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
  },
  headerTitle: { color: '#fff', fontSize: 20, fontWeight: '700' },
  headerSub: { color: '#B8D0F8', fontSize: 13, marginTop: 2 },
  logoutText: { color: '#B8D0F8', fontSize: 14 },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    margin: 16,
    marginBottom: 0,
    padding: 16,
    elevation: 2,
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
  },
  cardAlert: { borderLeftWidth: 4, borderLeftColor: '#F59E0B' },
  cardTitle: { fontSize: 15, fontWeight: '700', color: '#222', marginBottom: 12 },
  row: { flexDirection: 'row', marginBottom: 8 },
  stat: { flex: 1 },
  statLabel: { fontSize: 12, color: '#666', marginBottom: 2 },
  statValue: { fontSize: 16, fontWeight: '700', color: '#1B4F9C' },
  statValueAccent: { color: '#DC2626' },
  contratoRow: { paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#F0F4FA' },
  contratoCode: { fontWeight: '600', color: '#222', fontSize: 14 },
  contratoDetail: { color: '#666', fontSize: 13, marginTop: 2 },
  pendenciaRow: { paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#FEF3C7' },
  pendenciaTipo: { fontWeight: '600', color: '#B45309', fontSize: 13 },
  pendenciaDesc: { color: '#555', fontSize: 13 },
  emptyText: { color: '#888', textAlign: 'center', fontSize: 15 },
});
