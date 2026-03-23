import React, { useEffect, useRef, useState } from 'react';
import {
  View, Text, TextInput as RNTextInput, TouchableOpacity, StyleSheet, Alert,
  KeyboardAvoidingView, Platform, Keyboard, TouchableWithoutFeedback,
  ScrollView, ImageBackground,
} from 'react-native';
import * as SecureStore from 'expo-secure-store';
import { useRouter } from 'expo-router';
import { Eye, EyeOff, User as UserIcon } from 'lucide-react-native';
import { loginApi } from '@/services/api/authService';
import { useAuth } from '@/context/AuthContext';
import { maskCpf, onlyDigits, looksLikeEmail } from '@/utils/format';

const TEXT = '#ffffff';
const INPUT_BG = 'rgba(255,255,255,0.15)';
const INPUT_BORDER = 'rgba(255,255,255,0.35)';
const BTN_BG = '#ffffff';
const BTN_TEXT = '#692e44';

const bgImage = require('@/assets/female.png');

const REMEMBER_FLAG_KEY = '@Abase:rememberCpf';
const REMEMBER_CPF_KEY = '@Abase:rememberedCpf';

export default function LoginScreen() {
  const { login } = useAuth();
  const router = useRouter();

  const [loginField, setLoginField] = useState('');
  const [password, setPassword] = useState('');
  const [rememberCpf, setRememberCpf] = useState(true);
  const [busy, setBusy] = useState(false);
  const [showPass, setShowPass] = useState(false);

  const loginRef = useRef<RNTextInput>(null);
  const passRef = useRef<RNTextInput>(null);

  const isCpfMode = !/[A-Za-z@]/.test(loginField);

  useEffect(() => {
    (async () => {
      try {
        const flag = await SecureStore.getItemAsync(REMEMBER_FLAG_KEY);
        setRememberCpf(flag === null ? true : flag === '1');
        if (flag === '1' || flag === null) {
          const savedCpf = await SecureStore.getItemAsync(REMEMBER_CPF_KEY);
          if (savedCpf) setLoginField(maskCpf(savedCpf));
        }
      } catch {}
    })();
  }, []);

  useEffect(() => {
    setShowPass(false);
    setPassword(p => (isCpfMode ? onlyDigits(p) : p));
  }, [isCpfMode]);

  const handleLoginChange = (text: string) => {
    if (/[A-Za-z@]/.test(text)) {
      setLoginField(text);
      return;
    }
    setLoginField(maskCpf(text));
  };

  const persistRememberState = async (isEmail: boolean, rawLoginDigits: string) => {
    try {
      await SecureStore.setItemAsync(REMEMBER_FLAG_KEY, rememberCpf ? '1' : '0');
      if (rememberCpf && !isEmail && rawLoginDigits.length === 11) {
        await SecureStore.setItemAsync(REMEMBER_CPF_KEY, rawLoginDigits);
      } else {
        await SecureStore.deleteItemAsync(REMEMBER_CPF_KEY).catch(() => {});
      }
    } catch {}
  };

  const handleLogin = async () => {
    const rawLogin = (loginField || '').trim();
    const rawPass = (password || '').trim();

    if (!rawLogin || !rawPass) {
      Alert.alert('Atenção', 'Informe e-mail e senha, ou CPF e matrícula.');
      return;
    }

    const isEmail = looksLikeEmail(rawLogin);
    const loginDigits = isEmail ? '' : onlyDigits(rawLogin);
    const passDigits = isEmail ? rawPass : onlyDigits(rawPass);
    const payload = { login: isEmail ? rawLogin : loginDigits, password: passDigits };

    if (!isEmail && (!payload.login || !payload.password)) {
      Alert.alert('Atenção', 'Informe CPF e matrícula (apenas números).');
      return;
    }

    try {
      setBusy(true);
      const authPayload = await loginApi(payload);
      await login(authPayload);
      await persistRememberState(isEmail, loginDigits);
      router.replace('/(app)/(tabs)/');
    } catch (e: any) {
      const msg = e?.message || 'Falha ao entrar. Verifique seus dados e sua conexão.';
      Alert.alert('Erro', msg);
    } finally {
      setBusy(false);
    }
  };

  const passKey = `pass-${isCpfMode ? 'cpf' : 'email'}-${showPass ? 'vis' : 'hid'}`;
  const passPlaceholder = isCpfMode ? 'Matrícula (somente números)' : 'Senha do e-mail';

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.select({ ios: 'padding', android: undefined })}>
      <TouchableWithoutFeedback onPress={Keyboard.dismiss} accessible={false}>
        <ImageBackground source={bgImage} resizeMode="cover" style={styles.bg} imageStyle={styles.bgImage} blurRadius={0.5}>
          <View style={styles.overlay} />
          <ScrollView
            contentContainerStyle={styles.scroll}
            keyboardDismissMode={Platform.select({ ios: 'interactive', android: 'on-drag' })}
            keyboardShouldPersistTaps="handled"
          >
            <View style={styles.centerWrap}>
              <View style={styles.header}>
                <Text style={styles.brandWord}>ABASE</Text>
                <Text style={styles.subtitle}>
                  ASSOCIAÇÃO BENEFICENTE E ASSISTENCIAL DOS SERVIDORES PÚBLICOS
                </Text>
                <Text style={styles.slogan}>UNINDO FORÇAS EM PROL DE QUEM SERVE.</Text>
              </View>

              <View style={styles.formCard}>
                {/* Login (email/CPF) */}
                <View style={styles.inputRow}>
                  <UserIcon size={20} color="#fff" style={styles.leftIcon} />
                  <RNTextInput
                    ref={loginRef}
                    style={[styles.input, styles.inputWithLeft]}
                    placeholder="E-mail ou CPF"
                    placeholderTextColor="rgba(255,255,255,0.75)"
                    autoCapitalize="none"
                    autoCorrect={false}
                    keyboardType="default"
                    inputMode="text"
                    value={loginField}
                    onChangeText={handleLoginChange}
                    maxLength={isCpfMode ? 14 : 100}
                    returnKeyType="next"
                    onSubmitEditing={() => passRef.current?.focus()}
                  />
                </View>

                {/* Senha / Matrícula */}
                <View style={styles.inputRow}>
                  <RNTextInput
                    key={passKey}
                    ref={passRef}
                    style={[styles.input, styles.inputWithRight]}
                    placeholder={passPlaceholder}
                    placeholderTextColor="rgba(255,255,255,0.75)"
                    autoCapitalize="none"
                    autoCorrect={false}
                    secureTextEntry={!showPass}
                    value={password}
                    onChangeText={(t) => setPassword(isCpfMode ? onlyDigits(t) : t)}
                    returnKeyType="go"
                    onSubmitEditing={handleLogin}
                    keyboardType="default"
                    inputMode="text"
                    autoComplete={isCpfMode ? 'off' : 'password'}
                    textContentType={isCpfMode ? 'none' : 'password'}
                    importantForAutofill="no"
                  />
                  <TouchableOpacity
                    onPress={() => setShowPass(s => !s)}
                    style={styles.rightIconBtn}
                    hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
                  >
                    {showPass
                      ? <EyeOff size={22} color="#fff" />
                      : <Eye size={22} color="#fff" />
                    }
                  </TouchableOpacity>
                </View>

                {/* Lembrar CPF */}
                <TouchableOpacity
                  onPress={async () => {
                    const next = !rememberCpf;
                    setRememberCpf(next);
                    try { await SecureStore.setItemAsync(REMEMBER_FLAG_KEY, next ? '1' : '0'); } catch {}
                  }}
                  style={styles.rememberRow}
                  activeOpacity={0.8}
                >
                  <View style={[styles.checkbox, rememberCpf && styles.checkboxChecked]}>
                    {rememberCpf && <View style={styles.checkboxDot} />}
                  </View>
                  <Text style={styles.rememberText}>Lembrar meu CPF</Text>
                </TouchableOpacity>

                <TouchableOpacity style={[styles.button, busy && { opacity: 0.7 }]} onPress={handleLogin} disabled={busy}>
                  <Text style={styles.buttonText}>{busy ? 'Entrando...' : 'Entrar'}</Text>
                </TouchableOpacity>

                <View style={styles.createRow}>
                  <Text style={styles.createMuted}>Não tem conta?</Text>
                  <TouchableOpacity onPress={() => router.push('/(auth)/register')}>
                    <Text style={styles.createLink}>Criar conta</Text>
                  </TouchableOpacity>
                </View>

                <TouchableOpacity
                  onPress={() => router.push('/(auth)/forgot-password')}
                  style={styles.forgotBtn}
                  hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                >
                  <Text style={styles.forgotText}>Esqueci minha senha</Text>
                </TouchableOpacity>
              </View>
            </View>
          </ScrollView>
        </ImageBackground>
      </TouchableWithoutFeedback>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1, justifyContent: 'flex-end' },
  bgImage: { opacity: 1 },
  overlay: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(105,46,68,0.48)' },
  scroll: { flexGrow: 1, justifyContent: 'center', paddingHorizontal: 20, paddingBottom: 28, paddingTop: 28 },
  centerWrap: { width: '100%' },
  header: { alignItems: 'flex-start', marginBottom: 16 },
  brandWord: { color: TEXT, fontSize: 48, fontWeight: '900', letterSpacing: 6, marginTop: 6 },
  subtitle: { color: 'rgba(255,255,255,0.9)', fontSize: 12, letterSpacing: 1, marginTop: 6 },
  slogan: { color: TEXT, fontSize: 18, fontWeight: '800', marginTop: 14 },
  formCard: { marginTop: 18, backgroundColor: 'rgba(105,46,68,0.32)', padding: 14, borderRadius: 14, borderWidth: 1, borderColor: 'rgba(255,255,255,0.22)' },
  inputRow: { position: 'relative', marginBottom: 12, justifyContent: 'center' },
  leftIcon: { position: 'absolute', left: 12, zIndex: 5 },
  rightIconBtn: { position: 'absolute', right: 12, zIndex: 5 },
  input: { borderWidth: 1, borderColor: INPUT_BORDER, backgroundColor: INPUT_BG, color: TEXT, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16 },
  inputWithLeft: { paddingLeft: 40 },
  inputWithRight: { paddingRight: 42 },
  rememberRow: { flexDirection: 'row', alignItems: 'center', marginTop: 4, marginBottom: 12 },
  rememberText: { color: TEXT, marginLeft: 10 },
  checkbox: { width: 20, height: 20, borderRadius: 4, borderWidth: 1.5, borderColor: '#fff', alignItems: 'center', justifyContent: 'center', backgroundColor: 'transparent' },
  checkboxChecked: { backgroundColor: '#fff' },
  checkboxDot: { width: 10, height: 10, borderRadius: 2, backgroundColor: BTN_TEXT },
  button: { backgroundColor: BTN_BG, paddingVertical: 14, borderRadius: 28, alignItems: 'center', marginTop: 8 },
  buttonText: { color: BTN_TEXT, fontWeight: '800', fontSize: 16, letterSpacing: 0.4 },
  createRow: { flexDirection: 'row', alignItems: 'center', gap: 6, justifyContent: 'center', marginTop: 14 },
  createMuted: { color: 'rgba(255,255,255,0.9)' },
  createLink: { color: '#ffffff', fontWeight: '800', textDecorationLine: 'underline' },
  forgotBtn: { marginTop: 8, alignSelf: 'center' },
  forgotText: { color: '#ffffff', fontWeight: '700', textDecorationLine: 'underline' },
});
