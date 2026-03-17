import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { fetchAntecipacao } from '../api/app';
import type { HistoricoItem } from '../types';
import { formatCurrency, formatDate } from '../utils/formatters';

export default function AntecipacaoScreen() {
  const [historico, setHistorico] = useState<HistoricoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const { historico: data } = await fetchAntecipacao();
      setHistorico(data);
    } catch {
      Alert.alert('Erro', 'Não foi possível carregar o histórico.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#1B4F9C" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Histórico de Pagamentos</Text>
      </View>

      <FlatList
        data={historico}
        keyExtractor={(_, i) => String(i)}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              load();
            }}
          />
        }
        ListEmptyComponent={
          <Text style={styles.empty}>Nenhum pagamento encontrado.</Text>
        }
        contentContainerStyle={{ padding: 16 }}
        renderItem={({ item }) => (
          <View style={styles.itemCard}>
            <View style={styles.itemLeft}>
              <Text style={styles.itemCiclo}>Ciclo {item.ciclo_numero} · Parc. {item.numero_parcela}</Text>
              <Text style={styles.itemRef}>{formatDate(item.referencia_mes)}</Text>
              {item.data_pagamento && (
                <Text style={styles.itemData}>Pago em {formatDate(item.data_pagamento)}</Text>
              )}
            </View>
            <Text style={styles.itemValor}>{formatCurrency(item.valor)}</Text>
          </View>
        )}
      />
    </View>
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
  itemCard: {
    backgroundColor: '#fff',
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    elevation: 1,
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 1 },
  },
  itemLeft: {},
  itemCiclo: { fontWeight: '600', color: '#333', fontSize: 14 },
  itemRef: { color: '#666', fontSize: 13, marginTop: 2 },
  itemData: { color: '#16A34A', fontSize: 12, marginTop: 2 },
  itemValor: { fontWeight: '700', color: '#1B4F9C', fontSize: 16 },
});
