import React, { useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator, Alert, KeyboardAvoidingView, Platform, StatusBar,
  StyleSheet, Text, TextInput, TouchableOpacity, View,
  TouchableWithoutFeedback, Keyboard, ScrollView, ImageBackground,
} from 'react-native';
import { useRouter } from 'expo-router';
import { forgotPasswordApi } from '@/services/api/authService';
import { looksLikeEmail } from '@/utils/format';

const TEXT = '#ffffff';
const MUTED = 'rgba(255,255,255,0.85)';
const INPUT_BG = 'rgba(255,255,255,0.15)';
const INPUT_BORDER = 'rgba(255,255,255,0.35)';

const bgImage = require('@/assets/female.png');

export default function ForgotPasswordScreen() {
  const router = useRouter();
  const emailRef = useRef<TextInput>(null);
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState<{ message: string } | null>(null);

  const canSubmit = useMemo(() => looksLikeEmail(email) && !submitting, [email, submitting]);

  async function onSubmit() {
    if (!looksLikeEmail(email)) {
      Alert.alert('Atenção', 'Informe um e-mail válido.');
      return;
    }
    try {
      setSubmitting(true);
      const res = await forgotPasswordApi(email.trim());
      setDone({
        message: res?.message || 'Se existir uma conta com este e-mail, enviaremos as instruções de redefinição.',
      });
    } catch (e: any) {
      Alert.alert('Falha', e?.message || 'Não foi possível enviar o e-mail de recuperação.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.select({ ios: 'padding', android: undefined })}>
      <StatusBar barStyle="light-content" backgroundColor="rgba(0,0,0,0.2)" />
      <TouchableWithoutFeedback onPress={Keyboard.dismiss} accessible={false}>
        <ImageBackground source={bgImage} resizeMode="cover" style={styles.bg} imageStyle={{ opacity: 1 }} blurRadius={0.5}>
          <View style={styles.overlay} />
          <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
            <View style={styles.center}>
              <View style={styles.header}>
                <Text style={styles.brand}>ABASE</Text>
                <Text style={styles.subtitle}>ASSOCIAÇÃO BENEFICENTE E ASSISTENCIAL DOS SERVIDORES PÚBLICOS</Text>
                <Text style={styles.title}>Recuperar senha</Text>
                <Text style={styles.subtitle2}>Informe seu e-mail cadastrado para enviarmos as instruções de redefinição.</Text>
              </View>

              <View style={styles.card}>
                <Text style={styles.label}>E-mail</Text>
                <TextInput
                  ref={emailRef}
                  value={email}
                  onChangeText={setEmail}
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="email-address"
                  placeholder="seu@email.com"
                  placeholderTextColor={MUTED}
                  style={styles.input}
                  returnKeyType="send"
                  onSubmitEditing={onSubmit}
                  editable={!submitting}
                />
                <View style={{ height: 16 }} />
                <TouchableOpacity
                  style={[styles.button, { opacity: canSubmit ? 1 : 0.6 }]}
                  onPress={onSubmit}
                  disabled={!canSubmit}
                >
                  {submitting ? <ActivityIndicator /> : <Text style={styles.buttonText}>Enviar link</Text>}
                </TouchableOpacity>

                {done && (
                  <>
                    <View style={{ height: 18 }} />
                    <View style={styles.infoBox}>
                      <Text style={styles.infoText}>{done.message}</Text>
                    </View>
                  </>
                )}

                <View style={{ height: 24 }} />
                <TouchableOpacity onPress={() => router.back()} style={styles.backLink}>
                  <Text style={styles.backLinkText}>Voltar para o login</Text>
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
  bg: { flex: 1, justifyContent: 'center' },
  overlay: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(105,46,68,0.48)' },
  scroll: { flexGrow: 1, justifyContent: 'center', paddingHorizontal: 20, paddingVertical: 28 },
  center: { width: '100%' },
  header: { alignItems: 'flex-start', marginBottom: 14 },
  brand: { color: TEXT, fontSize: 48, fontWeight: '900', letterSpacing: 6, marginTop: 6 },
  subtitle: { color: 'rgba(255,255,255,0.9)', fontSize: 12, letterSpacing: 1, marginTop: 6 },
  title: { color: TEXT, fontSize: 20, fontWeight: '800', marginTop: 14 },
  subtitle2: { color: MUTED, fontSize: 14, marginTop: 4 },
  card: { marginTop: 10, backgroundColor: 'rgba(105,46,68,0.32)', padding: 16, borderRadius: 14, borderWidth: 1, borderColor: 'rgba(255,255,255,0.22)' },
  label: { color: TEXT, fontSize: 13, marginBottom: 6 },
  input: { height: 46, borderRadius: 12, borderWidth: 1, borderColor: INPUT_BORDER, paddingHorizontal: 12, color: TEXT, backgroundColor: INPUT_BG },
  button: { height: 48, borderRadius: 28, backgroundColor: '#ffffff', alignItems: 'center', justifyContent: 'center' },
  buttonText: { color: '#692e44', fontWeight: '800', fontSize: 16 },
  infoBox: { borderWidth: 1, borderColor: 'rgba(255,255,255,0.22)', borderRadius: 12, padding: 12, backgroundColor: 'rgba(105,46,68,0.22)' },
  infoText: { color: TEXT, fontSize: 13, lineHeight: 18 },
  backLink: { paddingVertical: 10, alignItems: 'center' },
  backLinkText: { color: TEXT, textDecorationLine: 'underline', fontWeight: '700' },
});
