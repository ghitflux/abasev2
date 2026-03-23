import React, { useEffect, useRef, useState } from 'react';
import {
  View, StatusBar, StyleSheet, Animated, Easing,
  useWindowDimensions, Text,
} from 'react-native';
import { useRouter } from 'expo-router';
import { useAuth } from '@/context/AuthContext';

const BG = '#692e44';
const FADE_IN_MS = 900;
const TYPE_MS = 85;
const HOLD_MS = 600;
const FULL_TEXT = 'Associação na palma da mão';

export default function SplashScreen() {
  const { token, loadingAuth } = useAuth();
  const router = useRouter();
  const { width: winW } = useWindowDimensions();

  const didNav = useRef(false);
  const fade = useRef(new Animated.Value(0)).current;
  const [typed, setTyped] = useState('');

  const BOX_W = Math.min(winW * 0.86, 480);
  const PAD_H = 18;
  const PAD_TOP = 14;
  const EXTRA_BOTTOM = 110;
  const LOGO_W = BOX_W * 0.72;
  const LOGO_H = LOGO_W / (1606 / 223);
  const BOX_H = LOGO_H + PAD_TOP + EXTRA_BOTTOM;

  useEffect(() => {
    if (loadingAuth) return;
    if (didNav.current) return;

    if (token) {
      didNav.current = true;
      router.replace('/(app)/(tabs)/');
      return;
    }

    Animated.timing(fade, {
      toValue: 1,
      duration: FADE_IN_MS,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();

    let i = 0;
    const interval = setInterval(() => {
      i += 1;
      setTyped(FULL_TEXT.slice(0, i));
      if (i >= FULL_TEXT.length) {
        clearInterval(interval);
        setTimeout(() => {
          if (!didNav.current) {
            didNav.current = true;
            router.replace('/(auth)/login');
          }
        }, HOLD_MS);
      }
    }, TYPE_MS);

    return () => clearInterval(interval);
  }, [loadingAuth, token, fade, router]);

  const animatedStyle = {
    opacity: fade,
    transform: [
      { translateY: fade.interpolate({ inputRange: [0, 1], outputRange: [20, 0] }) },
      { scale: fade.interpolate({ inputRange: [0, 1], outputRange: [0.95, 1] }) },
    ],
  };

  return (
    <View style={[styles.container, { backgroundColor: BG }]}>
      <StatusBar barStyle="light-content" backgroundColor={BG} />
      <Animated.View style={[styles.wrapper, animatedStyle]}>
        <View
          style={[
            styles.card,
            { width: BOX_W, height: BOX_H, paddingHorizontal: PAD_H, paddingTop: PAD_TOP, borderRadius: 26 },
          ]}
        >
          {/* Logo placeholder — substituir por SVG quando disponível */}
          <View style={{ alignItems: 'center', justifyContent: 'center' }}>
            <Text style={{ color: '#fff', fontSize: 40, fontWeight: '900', letterSpacing: 8 }}>
              ABASE
            </Text>
          </View>

          <View style={styles.titleArea}>
            <Text style={styles.titleText}>ABASE</Text>
          </View>

          <View style={styles.messageArea}>
            <Text style={styles.messageText}>
              {typed}
              <Text style={{ opacity: typed.length < FULL_TEXT.length ? 1 : 0 }}>▍</Text>
            </Text>
          </View>
        </View>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  wrapper: { alignItems: 'center', justifyContent: 'center' },
  card: {
    borderWidth: 4,
    borderColor: '#ffffff',
    backgroundColor: 'transparent',
    overflow: 'hidden',
    justifyContent: 'flex-start',
  },
  titleArea: { alignItems: 'center', justifyContent: 'center', marginTop: 8 },
  titleText: { color: '#ffffff', fontSize: 18, fontWeight: '700', letterSpacing: 2 },
  messageArea: { flex: 1, alignItems: 'center', justifyContent: 'flex-end', paddingBottom: 18 },
  messageText: { color: '#ffffff', fontSize: 16, fontWeight: '600', textAlign: 'center' },
});
