import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Alert, ActivityIndicator } from 'react-native';
import { User, CreditCard, Mail, Phone, CheckCheck, Clock, LogOut } from 'lucide-react-native';
import { useAuth } from '@/context/AuthContext';
import { logoutApi, getPerfilData, PerfilData } from '@/services/api/authService';

export default function PerfilScreen() {
  const { token, logout } = useAuth();
  const [data, setData] = useState<PerfilData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const perfil = await getPerfilData();
        setData(perfil);
      } catch (e: any) {
        Alert.alert('Atenção', e?.message || 'Não foi possível carregar seu perfil.');
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  const handleLogout = async () => {
    try {
      await logoutApi().catch(() => ({}));
    } finally {
      await logout();
    }
  };

  if (loading) {
    return (
      <View style={[s.container, { alignItems: 'center', justifyContent: 'center' }]}>
        <ActivityIndicator />
      </View>
    );
  }

  const cpfMasked = data?.cpfMasked || '—';
  const descontoTxt = `${data?.descontadas ?? 0}/${data?.total ?? 0}`;
  const statusTxt = data?.statusLabel || '—';

  return (
    <View style={s.container}>
      <Text style={s.title}>Meu Perfil</Text>
      <Text style={s.subtitle}>Gerencie suas informações pessoais</Text>

      <View style={s.card}>
        <Text style={s.section}>Informações Pessoais</Text>
        <Row Icon={User} label="Nome completo" value={data?.fullName || '—'} />
        <Row Icon={CreditCard} label="CPF/CNPJ" value={cpfMasked} />
        <Row Icon={Mail} label="E-mail" value={data?.email || '—'} />
        <Row Icon={Phone} label="Telefone" value={data?.phone || '—'} />
      </View>

      <View style={s.card}>
        <Text style={s.section}>Status da Conta</Text>
        <Row Icon={CheckCheck} label="Mensalidades descontadas" value={descontoTxt} />
        <Row Icon={Clock} label="Status" value={statusTxt} valueStyle={{ color: '#f59e0b' }} />
      </View>

      <TouchableOpacity style={s.logoutBtn} onPress={handleLogout}>
        <LogOut size={18} color="#fff" />
        <Text style={s.logoutTxt}>Sair da Conta</Text>
      </TouchableOpacity>
    </View>
  );
}

function Row({
  Icon, label, value, valueStyle,
}: {
  Icon: React.ComponentType<any>;
  label: string;
  value: string;
  valueStyle?: any;
}) {
  return (
    <View style={r.row}>
      <Icon size={18} color="#94a3b8" />
      <View style={{ flex: 1 }}>
        <Text style={r.label}>{label}</Text>
        <Text style={[r.value, valueStyle]}>{value}</Text>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a', padding: 16, gap: 14 },
  title: { color: '#e5e7eb', fontSize: 22, fontWeight: '700' },
  subtitle: { color: '#94a3b8', marginBottom: 2 },
  card: { backgroundColor: '#111827', padding: 16, borderRadius: 14 },
  section: { color: '#e5e7eb', fontWeight: '700', marginBottom: 10 },
  logoutBtn: { backgroundColor: '#b22222', padding: 14, borderRadius: 12, flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center' },
  logoutTxt: { color: '#fff', fontWeight: '700' },
});

const r = StyleSheet.create({
  row: { flexDirection: 'row', gap: 10, marginBottom: 10 },
  label: { color: '#94a3b8', fontSize: 12 },
  value: { color: '#e5e7eb', fontWeight: '600', marginTop: 2 },
});
