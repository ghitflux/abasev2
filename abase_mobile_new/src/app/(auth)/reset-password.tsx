import React, { useState, useRef } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, Alert,
  KeyboardAvoidingView, Platform, Keyboard, TouchableWithoutFeedback,
  ScrollView, ActivityIndicator, ImageBackground,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Eye, EyeOff } from 'lucide-react-native';
import { resetPasswordApi } from '@/services/api/authService';

const TEXT = '#ffffff';
const INPUT_BG = 'rgba(255,255,255,0.15)';
const INPUT_BORDER = 'rgba(255,255,255,0.35)';
const bgImage = require('@/assets/female.png');

export default function ResetPasswordScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ token?: string }>();

  const [token, setToken] = useState(params.token || '');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [busy, setBusy] = useState(false);

  const passRef = useRef<TextInput>(null);
  const confirmRef = useRef<TextInput>(null);

  async function onSubmit() {
    if (!token) {
      Alert.alert('Token inválido', 'Abra o link enviado por e-mail novamente.');
      return;
    }
    if (!password || password.length < 8) {
      Alert.alert('Senha fraca', 'A senha deve ter pelo menos 8 caracteres.');
      return;
    }
    if (password !== confirm) {
      Alert.alert('Senha divergente', 'As senhas não coincidem.');
      return;
    }

    try {
      setBusy(true);
      const res = await resetPasswordApi({ token, password, password_confirmation: confirm });
      Alert.alert('Senha redefinida!', res?.message || 'Sua senha foi alterada com sucesso.', [
        { text: 'Fazer login', onPress: () => router.replace('/(auth)/login') },
      ]);
    } catch (e: any) {
      Alert.alert('Erro', e?.message || 'Não foi possível redefinir a senha.');
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
            <View style={styles.card}>
              <Text style={styles.title}>Redefinir senha</Text>
              <Text style={styles.subtitle}>Informe o código do e-mail e a nova senha.</Text>

              <Text style={styles.label}>Código (token)</Text>
              <TextInput
                value={token}
                onChangeText={setToken}
                autoCapitalize="none"
                autoCorrect={false}
                placeholder="Cole o código do e-mail"
                placeholderTextColor="rgba(255,255,255,0.6)"
                style={styles.input}
                returnKeyType="next"
                onSubmitEditing={() => passRef.current?.focus()}
              />

              <Text style={[styles.label, { marginTop: 12 }]}>Nova senha</Text>
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
                  onSubmitEditing={() => confirmRef.current?.focus()}
                />
                <TouchableOpacity onPress={() => setShowPass(s => !s)} style={styles.eyeBtn}>
                  {showPass ? <EyeOff size={20} color="#fff" /> : <Eye size={20} color="#fff" />}
                </TouchableOpacity>
              </View>

              <Text style={[styles.label, { marginTop: 12 }]}>Confirmar nova senha</Text>
              <View style={styles.passRow}>
                <TextInput
                  ref={confirmRef}
                  value={confirm}
                  onChangeText={setConfirm}
                  secureTextEntry={!showConfirm}
                  placeholder="Repita a senha"
                  placeholderTextColor="rgba(255,255,255,0.6)"
                  style={[styles.input, { flex: 1 }]}
                  returnKeyType="go"
                  onSubmitEditing={onSubmit}
                />
                <TouchableOpacity onPress={() => setShowConfirm(s => !s)} style={styles.eyeBtn}>
                  {showConfirm ? <EyeOff size={20} color="#fff" /> : <Eye size={20} color="#fff" />}
                </TouchableOpacity>
              </View>

              <View style={{ height: 20 }} />
              <TouchableOpacity
                style={[styles.button, busy && { opacity: 0.7 }]}
                onPress={onSubmit}
                disabled={busy}
              >
                {busy ? <ActivityIndicator /> : <Text style={styles.buttonText}>Redefinir senha</Text>}
              </TouchableOpacity>

              <TouchableOpacity onPress={() => router.back()} style={styles.backLink}>
                <Text style={styles.backLinkText}>Cancelar</Text>
              </TouchableOpacity>
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
  card: { backgroundColor: 'rgba(105,46,68,0.32)', padding: 16, borderRadius: 14, borderWidth: 1, borderColor: 'rgba(255,255,255,0.22)' },
  title: { color: TEXT, fontSize: 22, fontWeight: '900', marginBottom: 6 },
  subtitle: { color: 'rgba(255,255,255,0.8)', fontSize: 14, marginBottom: 16 },
  label: { color: TEXT, fontSize: 13, marginBottom: 6 },
  input: { height: 46, borderRadius: 12, borderWidth: 1, borderColor: INPUT_BORDER, paddingHorizontal: 12, color: TEXT, backgroundColor: INPUT_BG },
  passRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  eyeBtn: { padding: 10 },
  button: { height: 48, borderRadius: 28, backgroundColor: '#ffffff', alignItems: 'center', justifyContent: 'center' },
  buttonText: { color: '#692e44', fontWeight: '800', fontSize: 16 },
  backLink: { paddingVertical: 12, alignItems: 'center' },
  backLinkText: { color: TEXT, textDecorationLine: 'underline', fontWeight: '600' },
});
