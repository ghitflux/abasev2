import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';
import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';

import { fetchPendencias, uploadDocumento } from '../api/app';
import type { Pendencia } from '../types';
import { formatDate } from '../utils/formatters';

const TIPO_LABELS: Record<string, string> = {
  DOCUMENTO: 'Documento',
  FINANCEIRO: 'Financeiro',
  CADASTRO: 'Cadastro',
};

export default function PendenciasScreen() {
  const [pendencias, setPendencias] = useState<Pendencia[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [uploading, setUploading] = useState(false);

  const load = useCallback(async () => {
    try {
      const { pendencias: data } = await fetchPendencias();
      setPendencias(data);
    } catch {
      Alert.alert('Erro', 'Não foi possível carregar as pendências.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleUpload() {
    Alert.alert('Enviar documento', 'Escolha a origem do arquivo', [
      { text: 'Câmera / Galeria', onPress: pickImage },
      { text: 'Arquivo PDF', onPress: pickDocument },
      { text: 'Cancelar', style: 'cancel' },
    ]);
  }

  async function pickImage() {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
    });
    if (!result.canceled && result.assets[0]) {
      const asset = result.assets[0];
      await sendFile(asset.uri, asset.fileName ?? 'foto.jpg', asset.mimeType ?? 'image/jpeg');
    }
  }

  async function pickDocument() {
    const result = await DocumentPicker.getDocumentAsync({ type: 'application/pdf' });
    if (!result.canceled && result.assets[0]) {
      const asset = result.assets[0];
      await sendFile(asset.uri, asset.name, asset.mimeType ?? 'application/pdf');
    }
  }

  async function sendFile(uri: string, name: string, mimeType: string) {
    setUploading(true);
    try {
      await uploadDocumento('outro', uri, name, mimeType);
      Alert.alert('Sucesso', 'Documento enviado com sucesso!');
      load();
    } catch {
      Alert.alert('Erro', 'Não foi possível enviar o documento. Tente novamente.');
    } finally {
      setUploading(false);
    }
  }

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
        <Text style={styles.headerTitle}>Pendências de Documentos</Text>
      </View>

      <FlatList
        data={pendencias}
        keyExtractor={(item) => String(item.id)}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => { setRefreshing(true); load(); }}
          />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyIcon}>✅</Text>
            <Text style={styles.empty}>Nenhuma pendência! Tudo em ordem.</Text>
          </View>
        }
        contentContainerStyle={{ padding: 16 }}
        renderItem={({ item }) => (
          <View style={styles.itemCard}>
            <View style={styles.itemHeader}>
              <Text style={styles.itemTipo}>{TIPO_LABELS[item.tipo] ?? item.tipo}</Text>
              <View style={[
                styles.statusBadge,
                item.status === 'ABERTA' ? styles.statusAberta : styles.statusResolvida,
              ]}>
                <Text style={styles.statusText}>{item.status}</Text>
              </View>
            </View>
            <Text style={styles.itemDesc}>{item.descricao}</Text>
            <Text style={styles.itemData}>Aberta em {formatDate(item.created_at.split('T')[0])}</Text>
          </View>
        )}
        ListFooterComponent={
          <TouchableOpacity
            style={[styles.uploadButton, uploading && styles.uploadDisabled]}
            onPress={handleUpload}
            disabled={uploading}
          >
            {uploading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.uploadText}>📎 Enviar Documento</Text>
            )}
          </TouchableOpacity>
        }
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
  emptyContainer: { alignItems: 'center', marginTop: 40 },
  emptyIcon: { fontSize: 48, marginBottom: 12 },
  empty: { textAlign: 'center', color: '#888', fontSize: 15 },
  itemCard: {
    backgroundColor: '#fff',
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
    elevation: 1,
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 1 },
  },
  itemHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  itemTipo: { fontWeight: '700', color: '#333', fontSize: 14 },
  statusBadge: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  statusAberta: { backgroundColor: '#FEE2E2' },
  statusResolvida: { backgroundColor: '#DCFCE7' },
  statusText: { fontSize: 11, fontWeight: '600', color: '#333' },
  itemDesc: { color: '#555', fontSize: 13, marginBottom: 4 },
  itemData: { color: '#999', fontSize: 12 },
  uploadButton: {
    backgroundColor: '#1B4F9C',
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 16,
    marginBottom: 8,
  },
  uploadDisabled: { opacity: 0.6 },
  uploadText: { color: '#fff', fontWeight: '700', fontSize: 15 },
});
