import React, { useState, useRef } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, Alert,
  KeyboardAvoidingView, Platform, Keyboard, TouchableWithoutFeedback,
  ScrollView, ActivityIndicator, ImageBackground,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Eye, EyeOff } from 'lucide-react-native';
import { registerApi } from '@/services/api/authService';
import { useAuth } from '@/context/AuthContext';
import { looksLikeEmail } from '@/utils/format';

const TEXT = '#ffffff';
const INPUT_BG = 'rgba(255,255,255,0.15)';
const INPUT_BORDER = 'rgba(255,255,255,0.35)';
const TERMS_VERSION = '1.0';

const bgImage = require('@/assets/female.png');

export default function RegisterScreen() {
  const router = useRouter();
  const { login } = useAuth();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [password2, setPassword2] = useState('');
  const [terms, setTerms] = useState(false);
  const [showPass, setShowPass] = useState(false);
  const [showPass2, setShowPass2] = useState(false);
  const [busy, setBusy] = useState(false);

  const emailRef = useRef<TextInput>(null);
  const passRef = useRef<TextInput>(null);
  const pass2Ref = useRef<TextInput>(null);

  async function handleRegister() {
    if (!name.trim()) { Alert.alert('Atenção', 'Informe seu nome completo.'); return; }
    if (!looksLikeEmail(email)) { Alert.alert('Atenção', 'Informe um e-mail válido.'); return; }
    if (password.length < 8) { Alert.alert('Atenção', 'A senha deve ter pelo menos 8 caracteres.'); return; }
    if (password !== password2) { Alert.alert('Atenção', 'As senhas não coincidem.'); return; }
    if (!terms) { Alert.alert('Atenção', 'Você precisa aceitar os termos para continuar.'); return; }

    try {
      setBusy(true);
      const res = await registerApi({
        name: name.trim(),
        email: email.trim().toLowerCase(),
        password,
        password_confirmation: password2,
        terms: true,
        terms_version: TERMS_VERSION,
      });

      if (res?.token && res?.user) {
        await login({
          token: res.token,
          refreshToken: res.refreshToken ?? null,
          user: res.user,
          roles: res.roles || [],
        });
        router.replace('/(app)/(tabs)');
      } else {
        Alert.alert('Conta criada!', res?.message || 'Conta criada com sucesso. Faça login para continuar.', [
          { text: 'Fazer login', onPress: () => router.replace('/(auth)/login') },
        ]);
      }
    } catch (e: any) {
      Alert.alert('Erro', e?.message || 'Não foi possível criar a conta.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.select({ ios: 'padding', android: undefined })}>
      <TouchableWithoutFeedback onPress={Keyboard.dismiss} accessible={false}>
        <ImageBackground source={bgImage} resizeMode="cover" style={styles.bg} blurRadius={0.5}>
          <View style={styles.overlay} />
          <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
            <View style={styles.center}>
              <Text style={styles.brand}>ABASE</Text>
              <Text style={styles.subtitle}>Crie sua conta</Text>

              <View style={styles.card}>
                <Text style={styles.label}>Nome completo</Text>
                <TextInput
                  value={name}
                  onChangeText={setName}
                  placeholder="Seu nome completo"
                  placeholderTextColor="rgba(255,255,255,0.6)"
                  style={styles.input}
                  returnKeyType="next"
                  autoCapitalize="words"
                  onSubmitEditing={() => emailRef.current?.focus()}
                />

                <Text style={[styles.label, { marginTop: 12 }]}>E-mail</Text>
                <TextInput
                  ref={emailRef}
                  value={email}
                  onChangeText={setEmail}
                  placeholder="seu@email.com"
                  placeholderTextColor="rgba(255,255,255,0.6)"
                  style={styles.input}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoCorrect={false}
                  returnKeyType="next"
                  onSubmitEditing={() => passRef.current?.focus()}
                />

                <Text style={[styles.label, { marginTop: 12 }]}>Senha</Text>
                <View style={styles.passRow}>
                  <TextInput
                    ref={passRef}
                    value={password}
                    onChangeText={setPassword}
                    secureTextEntry={!showPass}
                    placeholder="Mínimo 8 caracteres"
                    placeholderTextColor="rgba(255,255,255,0.6)"
                    style={[styles.input, { flex: 1 }]}
                    returnKeyType="next"
                    onSubmitEditing={() => pass2Ref.current?.focus()}
                  />
                  <TouchableOpacity onPress={() => setShowPass(s => !s)} style={styles.eyeBtn}>
                    {showPass ? <EyeOff size={20} color="#fff" /> : <Eye size={20} color="#fff" />}
                  </TouchableOpacity>
                </View>

                <Text style={[styles.label, { marginTop: 12 }]}>Confirmar senha</Text>
                <View style={styles.passRow}>
                  <TextInput
                    ref={pass2Ref}
                    value={password2}
                    onChangeText={setPassword2}
                    secureTextEntry={!showPass2}
                    placeholder="Repita a senha"
                    placeholderTextColor="rgba(255,255,255,0.6)"
                    style={[styles.input, { flex: 1 }]}
                    returnKeyType="go"
                    onSubmitEditing={handleRegister}
                  />
                  <TouchableOpacity onPress={() => setShowPass2(s => !s)} style={styles.eyeBtn}>
                    {showPass2 ? <EyeOff size={20} color="#fff" /> : <Eye size={20} color="#fff" />}
                  </TouchableOpacity>
                </View>

                {/* Termos */}
                <TouchableOpacity
                  onPress={() => setTerms(t => !t)}
                  style={styles.termsRow}
                  activeOpacity={0.8}
                >
                  <View style={[styles.checkbox, terms && styles.checkboxChecked]}>
                    {terms && <View style={styles.checkboxDot} />}
                  </View>
                  <Text style={styles.termsText}>
                    Aceito os{' '}
                    <Text style={{ textDecorationLine: 'underline', fontWeight: '700' }}>
                      termos de uso e privacidade
                    </Text>
                  </Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.button, busy && { opacity: 0.7 }]}
                  onPress={handleRegister}
                  disabled={busy}
                >
                  {busy ? <ActivityIndicator /> : <Text style={styles.buttonText}>Criar conta</Text>}
                </TouchableOpacity>

                <View style={styles.loginRow}>
                  <Text style={{ color: 'rgba(255,255,255,0.9)' }}>Já tem conta?</Text>
                  <TouchableOpacity onPress={() => router.back()}>
                    <Text style={styles.loginLink}>Fazer login</Text>
                  </TouchableOpacity>
                </View>
              </View>
            </View>
          </ScrollView>
        </ImageBackground>
      </TouchableWithoutFeedback>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1 },
  overlay: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(105,46,68,0.48)' },
  scroll: { flexGrow: 1, justifyContent: 'center', paddingHorizontal: 20, paddingVertical: 28 },
  center: { width: '100%' },
  brand: { color: TEXT, fontSize: 48, fontWeight: '900', letterSpacing: 6, marginBottom: 4 },
  subtitle: { color: 'rgba(255,255,255,0.9)', fontSize: 18, fontWeight: '700', marginBottom: 16 },
  card: { backgroundColor: 'rgba(105,46,68,0.32)', padding: 16, borderRadius: 14, borderWidth: 1, borderColor: 'rgba(255,255,255,0.22)' },
  label: { color: TEXT, fontSize: 13, marginBottom: 6 },
  input: { height: 46, borderRadius: 12, borderWidth: 1, borderColor: INPUT_BORDER, paddingHorizontal: 12, color: TEXT, backgroundColor: INPUT_BG },
  passRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  eyeBtn: { padding: 10 },
  termsRow: { flexDirection: 'row', alignItems: 'center', marginTop: 16, marginBottom: 12, gap: 10 },
  termsText: { color: TEXT, flex: 1 },
  checkbox: { width: 20, height: 20, borderRadius: 4, borderWidth: 1.5, borderColor: '#fff', alignItems: 'center', justifyContent: 'center' },
  checkboxChecked: { backgroundColor: '#fff' },
  checkboxDot: { width: 10, height: 10, borderRadius: 2, backgroundColor: '#692e44' },
  button: { height: 48, borderRadius: 28, backgroundColor: '#ffffff', alignItems: 'center', justifyContent: 'center' },
  buttonText: { color: '#692e44', fontWeight: '800', fontSize: 16 },
  loginRow: { flexDirection: 'row', alignItems: 'center', gap: 6, justifyContent: 'center', marginTop: 14 },
  loginLink: { color: '#fff', fontWeight: '800', textDecorationLine: 'underline' },
});
