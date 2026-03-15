import React, { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';

import { criarAssociado, validarCpf } from '../api/associados';
import { cleanCpf, formatCpf } from '../utils/formatters';

const INITIAL = {
  nome_completo: '',
  cpf_cnpj: '',
  email: '',
  telefone: '',
  cargo: '',
  orgao_publico: '',
  matricula_orgao: '',
};

export default function CadastroAssociadoScreen() {
  const [form, setForm] = useState(INITIAL);
  const [loading, setLoading] = useState(false);
  const [cpfChecked, setCpfChecked] = useState(false);

  function set(field: keyof typeof INITIAL, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (field === 'cpf_cnpj') setCpfChecked(false);
  }

  async function checkCpf() {
    const digits = cleanCpf(form.cpf_cnpj);
    if (digits.length !== 11) {
      Alert.alert('CPF inválido', 'Informe um CPF com 11 dígitos.');
      return;
    }
    setLoading(true);
    try {
      const result = await validarCpf(digits);
      if (result.exists) {
        Alert.alert('CPF já cadastrado', result.message ?? 'Este CPF já possui cadastro.');
      } else {
        setCpfChecked(true);
      }
    } catch {
      Alert.alert('Erro', 'Não foi possível verificar o CPF.');
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit() {
    if (!form.nome_completo || !form.cpf_cnpj || !form.email) {
      Alert.alert('Campos obrigatórios', 'Preencha nome, CPF e e-mail.');
      return;
    }
    if (!cpfChecked) {
      Alert.alert('Verificação pendente', 'Verifique o CPF antes de continuar.');
      return;
    }

    setLoading(true);
    try {
      const payload = { ...form, cpf_cnpj: cleanCpf(form.cpf_cnpj) };
      const result = await criarAssociado(payload);
      Alert.alert('Sucesso!', `Associado cadastrado. ID: ${result.id}`);
      setForm(INITIAL);
      setCpfChecked(false);
    } catch (error: unknown) {
      const data = (error as { response?: { data?: Record<string, unknown> } })?.response?.data;
      const msg = data ? JSON.stringify(data) : 'Não foi possível cadastrar.';
      Alert.alert('Erro ao cadastrar', msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Cadastrar Associado</Text>
        </View>

        <View style={styles.form}>
          <Label>Nome completo *</Label>
          <TextInput
            style={styles.input}
            value={form.nome_completo}
            onChangeText={(v) => set('nome_completo', v)}
            placeholder="Nome completo"
            autoCapitalize="words"
          />

          <Label>CPF *</Label>
          <View style={styles.cpfRow}>
            <TextInput
              style={[styles.input, { flex: 1, marginBottom: 0 }]}
              value={formatCpf(form.cpf_cnpj)}
              onChangeText={(v) => set('cpf_cnpj', v)}
              keyboardType="numeric"
              placeholder="000.000.000-00"
              maxLength={14}
            />
            <TouchableOpacity
              style={[styles.checkButton, cpfChecked && styles.checkButtonOk]}
              onPress={checkCpf}
              disabled={loading}
            >
              <Text style={styles.checkButtonText}>{cpfChecked ? '✓ OK' : 'Verificar'}</Text>
            </TouchableOpacity>
          </View>

          <Label>E-mail *</Label>
          <TextInput
            style={styles.input}
            value={form.email}
            onChangeText={(v) => set('email', v)}
            keyboardType="email-address"
            autoCapitalize="none"
            placeholder="email@exemplo.com"
          />

          <Label>Telefone</Label>
          <TextInput
            style={styles.input}
            value={form.telefone}
            onChangeText={(v) => set('telefone', v)}
            keyboardType="phone-pad"
            placeholder="(00) 00000-0000"
          />

          <Label>Órgão público</Label>
          <TextInput
            style={styles.input}
            value={form.orgao_publico}
            onChangeText={(v) => set('orgao_publico', v)}
            placeholder="Prefeitura, Secretaria..."
          />

          <Label>Cargo</Label>
          <TextInput
            style={styles.input}
            value={form.cargo}
            onChangeText={(v) => set('cargo', v)}
            placeholder="Cargo ou função"
          />

          <Label>Matrícula do órgão</Label>
          <TextInput
            style={styles.input}
            value={form.matricula_orgao}
            onChangeText={(v) => set('matricula_orgao', v)}
            placeholder="Número da matrícula"
          />

          <TouchableOpacity
            style={[styles.submitButton, loading && styles.submitDisabled]}
            onPress={handleSubmit}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.submitText}>Cadastrar</Text>
            )}
          </TouchableOpacity>
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <Text style={styles.label}>{children}</Text>;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F0F4FA' },
  header: {
    backgroundColor: '#1B4F9C',
    paddingTop: 56,
    paddingBottom: 16,
    paddingHorizontal: 20,
  },
  headerTitle: { color: '#fff', fontSize: 20, fontWeight: '700' },
  form: { padding: 16 },
  label: { fontSize: 13, fontWeight: '600', color: '#333', marginBottom: 4, marginTop: 12 },
  input: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#DDE',
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: '#222',
    marginBottom: 4,
  },
  cpfRow: { flexDirection: 'row', gap: 8, marginBottom: 4 },
  checkButton: {
    backgroundColor: '#1B4F9C',
    borderRadius: 8,
    paddingHorizontal: 14,
    justifyContent: 'center',
  },
  checkButtonOk: { backgroundColor: '#16A34A' },
  checkButtonText: { color: '#fff', fontWeight: '600', fontSize: 13 },
  submitButton: {
    backgroundColor: '#1B4F9C',
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 24,
  },
  submitDisabled: { opacity: 0.6 },
  submitText: { color: '#fff', fontWeight: '700', fontSize: 16 },
});
