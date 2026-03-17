import React, { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';

import { useAuth } from '../context/AuthContext';
import { cleanCpf, formatCpf } from '../utils/formatters';

export default function LoginScreen() {
  const { login } = useAuth();
  const [cpf, setCpf] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  function handleCpfChange(text: string) {
    setCpf(formatCpf(text));
  }

  async function handleLogin() {
    const cpfDigits = cleanCpf(cpf);
    if (cpfDigits.length !== 11) {
      Alert.alert('CPF inválido', 'Informe um CPF com 11 dígitos.');
      return;
    }
    if (!password) {
      Alert.alert('Senha obrigatória', 'Informe sua senha.');
      return;
    }

    setLoading(true);
    try {
      await login(cpfDigits, password, true);
    } catch (error: unknown) {
      const msg =
        (error as { response?: { data?: { detail?: string; non_field_errors?: string[] } } })
          ?.response?.data?.detail ??
        (error as { response?: { data?: { non_field_errors?: string[] } } })
          ?.response?.data?.non_field_errors?.[0] ??
        'Verifique seu CPF e senha.';
      Alert.alert('Erro ao entrar', msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={styles.card}>
        <Text style={styles.logo}>ABASE</Text>
        <Text style={styles.subtitle}>Associação Beneficente</Text>

        <Text style={styles.label}>CPF</Text>
        <TextInput
          style={styles.input}
          value={cpf}
          onChangeText={handleCpfChange}
          keyboardType="numeric"
          placeholder="000.000.000-00"
          placeholderTextColor="#AAB"
          maxLength={14}
          autoComplete="off"
        />

        <Text style={styles.label}>Senha</Text>
        <TextInput
          style={styles.input}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          placeholder="Sua senha"
          placeholderTextColor="#AAB"
          autoComplete="off"
        />

        <TouchableOpacity
          style={[styles.button, loading && styles.buttonDisabled]}
          onPress={handleLogin}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.buttonText}>Entrar</Text>
          )}
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1B4F9C',
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 28,
    elevation: 8,
    shadowColor: '#000',
    shadowOpacity: 0.15,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
  },
  logo: {
    fontSize: 36,
    fontWeight: '900',
    color: '#1B4F9C',
    textAlign: 'center',
    letterSpacing: 4,
  },
  subtitle: {
    fontSize: 13,
    color: '#666',
    textAlign: 'center',
    marginBottom: 28,
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  input: {
    borderWidth: 1,
    borderColor: '#DDE',
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    color: '#222',
    marginBottom: 16,
  },
  button: {
    backgroundColor: '#1B4F9C',
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 8,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 16,
  },
});
