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

import { fetchMensalidades } from '../api/app';
import type { Ciclo } from '../types';
import { formatCurrency, formatDate, statusParcelaLabel } from '../utils/formatters';

const STATUS_COLOR: Record<string, string> = {
  descontado: '#16A34A',
  em_aberto: '#1B4F9C',
  futuro: '#9CA3AF',
  nao_descontado: '#DC2626',
  cancelado: '#6B7280',
};

export default function MensalidadesScreen() {
  const [ciclos, setCiclos] = useState<Ciclo[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [expandedCiclo, setExpandedCiclo] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const { ciclos: data } = await fetchMensalidades();
      setCiclos(data);
      if (data.length > 0 && expandedCiclo === null) {
        setExpandedCiclo(data[0].id);
      }
    } catch {
      Alert.alert('Erro', 'Não foi possível carregar as mensalidades.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [expandedCiclo]);

  useEffect(() => {
    load();
  }, []);

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#1B4F9C" />
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
    >
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Parcelas por Ciclo</Text>
      </View>

      {ciclos.length === 0 && (
        <Text style={styles.empty}>Nenhum ciclo encontrado.</Text>
      )}

      {ciclos.map((ciclo) => {
        const isOpen = expandedCiclo === ciclo.id;
        const pagas = ciclo.parcelas.filter((p) => p.status === 'descontado').length;

        return (
          <View key={ciclo.id} style={styles.cicloCard}>
            <TouchableOpacity
              style={styles.cicloHeader}
              onPress={() => setExpandedCiclo(isOpen ? null : ciclo.id)}
            >
              <View>
                <Text style={styles.cicloTitle}>Ciclo {ciclo.numero}</Text>
                <Text style={styles.cicloSub}>
                  {formatDate(ciclo.data_inicio)} – {formatDate(ciclo.data_fim)}
                </Text>
              </View>
              <View style={styles.cicloRight}>
                <Text style={styles.cicloProgress}>{pagas}/{ciclo.parcelas.length} pagas</Text>
                <Text style={styles.expandIcon}>{isOpen ? '▲' : '▼'}</Text>
              </View>
            </TouchableOpacity>

            {isOpen && (
              <View style={styles.parcelasContainer}>
                {ciclo.parcelas.map((parcela) => (
                  <View key={parcela.numero} style={styles.parcelaRow}>
                    <View style={styles.parcelaLeft}>
                      <Text style={styles.parcelaNum}>Parc. {parcela.numero}</Text>
                      <Text style={styles.parcelaRef}>{formatDate(parcela.referencia_mes)}</Text>
                    </View>
                    <View style={styles.parcelaRight}>
                      <Text style={styles.parcelaValor}>{formatCurrency(parcela.valor)}</Text>
                      <View
                        style={[
                          styles.statusBadge,
                          { backgroundColor: (STATUS_COLOR[parcela.status] ?? '#9CA3AF') + '22' },
                        ]}
                      >
                        <Text
                          style={[
                            styles.statusText,
                            { color: STATUS_COLOR[parcela.status] ?? '#9CA3AF' },
                          ]}
                        >
                          {statusParcelaLabel(parcela.status)}
                        </Text>
                      </View>
                      {parcela.data_pagamento && (
                        <Text style={styles.dataPag}>
                          Pago em {formatDate(parcela.data_pagamento)}
                        </Text>
                      )}
                    </View>
                  </View>
                ))}
              </View>
            )}
          </View>
        );
      })}

      <View style={{ height: 24 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F0F4FA' },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: {
    backgroundColor: '#1B4F9C',
    paddingTop: 56,
    paddingBottom: 16,
    paddingHorizontal: 20,
  },
  headerTitle: { color: '#fff', fontSize: 20, fontWeight: '700' },
  empty: { textAlign: 'center', color: '#888', marginTop: 40, fontSize: 15 },
  cicloCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    margin: 16,
    marginBottom: 0,
    elevation: 2,
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    overflow: 'hidden',
  },
  cicloHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    backgroundColor: '#F8FAFF',
  },
  cicloTitle: { fontWeight: '700', fontSize: 15, color: '#1B4F9C' },
  cicloSub: { fontSize: 12, color: '#666', marginTop: 2 },
  cicloRight: { alignItems: 'flex-end' },
  cicloProgress: { fontWeight: '600', color: '#16A34A', fontSize: 13 },
  expandIcon: { color: '#9CA3AF', marginTop: 4 },
  parcelasContainer: { paddingHorizontal: 16, paddingBottom: 8 },
  parcelaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#F0F4FA',
  },
  parcelaLeft: {},
  parcelaNum: { fontWeight: '600', color: '#333', fontSize: 14 },
  parcelaRef: { fontSize: 12, color: '#888', marginTop: 2 },
  parcelaRight: { alignItems: 'flex-end' },
  parcelaValor: { fontWeight: '700', color: '#222', fontSize: 15 },
  statusBadge: {
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 2,
    marginTop: 4,
  },
  statusText: { fontSize: 12, fontWeight: '600' },
  dataPag: { fontSize: 11, color: '#888', marginTop: 2 },
});
