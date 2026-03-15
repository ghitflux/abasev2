import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';

import { fetchMe } from '../api/app';
import { useAuth } from '../context/AuthContext';
import type { AssociadoMobile } from '../types';
import { formatCpf, statusAssociadoLabel } from '../utils/formatters';

export default function PerfilScreen() {
  const { user, logout, hasRole } = useAuth();
  const [associado, setAssociado] = useState<AssociadoMobile | null>(null);
  const [loading, setLoading] = useState(true);

  const isAssociado = hasRole('ASSOCIADO');

  const load = useCallback(async () => {
    if (!isAssociado) {
      setLoading(false);
      return;
    }
    try {
      const data = await fetchMe();
      setAssociado(data.associado);
    } catch {
      // silencioso — mostra apenas dados do user
    } finally {
      setLoading(false);
    }
  }, [isAssociado]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.avatar}>{user?.first_name?.[0] ?? 'A'}</Text>
        <Text style={styles.name}>{user?.full_name ?? user?.email}</Text>
        <Text style={styles.role}>{user?.primary_role ?? 'USUÁRIO'}</Text>
      </View>

      {loading ? (
        <View style={styles.centered}>
          <ActivityIndicator color="#1B4F9C" />
        </View>
      ) : (
        <View style={styles.section}>
          {associado && (
            <>
              <InfoRow label="CPF" value={formatCpf(associado.cpf_cnpj)} />
              <InfoRow label="Matrícula" value={associado.matricula} />
              <InfoRow label="Status" value={statusAssociadoLabel(associado.status)} />
              <InfoRow label="Telefone" value={associado.telefone || '—'} />
              <InfoRow label="E-mail" value={associado.email || '—'} />
              <InfoRow label="Órgão público" value={associado.orgao_publico || '—'} />
              <InfoRow label="Cargo" value={associado.cargo || '—'} />
            </>
          )}
          {!associado && (
            <InfoRow label="E-mail" value={user?.email ?? '—'} />
          )}
        </View>
      )}

      <TouchableOpacity style={styles.logoutButton} onPress={logout}>
        <Text style={styles.logoutText}>Sair da conta</Text>
      </TouchableOpacity>

      <View style={{ height: 32 }} />
    </ScrollView>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F0F4FA' },
  centered: { padding: 24, alignItems: 'center' },
  header: {
    backgroundColor: '#1B4F9C',
    paddingTop: 56,
    paddingBottom: 28,
    alignItems: 'center',
  },
  avatar: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: '#fff',
    textAlign: 'center',
    lineHeight: 72,
    fontSize: 32,
    fontWeight: '700',
    color: '#1B4F9C',
    overflow: 'hidden',
  },
  name: { color: '#fff', fontSize: 18, fontWeight: '700', marginTop: 12 },
  role: { color: '#B8D0F8', fontSize: 13, marginTop: 4 },
  section: {
    backgroundColor: '#fff',
    margin: 16,
    borderRadius: 12,
    overflow: 'hidden',
    elevation: 2,
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 13,
    borderBottomWidth: 1,
    borderBottomColor: '#F0F4FA',
  },
  infoLabel: { fontSize: 14, color: '#666', flex: 1 },
  infoValue: { fontSize: 14, fontWeight: '500', color: '#222', flex: 2, textAlign: 'right' },
  logoutButton: {
    marginHorizontal: 16,
    backgroundColor: '#FEE2E2',
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
  },
  logoutText: { color: '#DC2626', fontWeight: '700', fontSize: 15 },
});
