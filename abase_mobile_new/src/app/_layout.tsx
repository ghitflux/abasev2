import { useEffect, useState } from 'react';
import { View, ActivityIndicator } from 'react-native';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { AuthProvider } from '@/context/AuthContext';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import MaintenanceScreen from '@/components/MaintenanceScreen';
import { ENDPOINTS } from '@/services/api/constants';

// Mantém a splash nativa visível até o app estar pronto
SplashScreen.preventAutoHideAsync();

type AppStatus = { maintenance: boolean; message: string } | null;

async function fetchAppStatus(): Promise<AppStatus> {
  try {
    const res = await fetch(ENDPOINTS.appStatus, { method: 'GET' });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export default function RootLayout() {
  const [appStatus, setAppStatus] = useState<AppStatus>(null);
  const [statusChecked, setStatusChecked] = useState(false);

  useEffect(() => {
    fetchAppStatus().then((s) => {
      setAppStatus(s);
      setStatusChecked(true);
      SplashScreen.hideAsync();
    });
  }, []);

  if (!statusChecked) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0b1222' }}>
        <ActivityIndicator color="#f472b6" size="large" />
      </View>
    );
  }

  if (appStatus?.maintenance) {
    return (
      <GestureHandlerRootView style={{ flex: 1 }}>
        <SafeAreaProvider>
          <MaintenanceScreen message={appStatus.message} />
        </SafeAreaProvider>
      </GestureHandlerRootView>
    );
  }

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <AuthProvider>
          <Stack screenOptions={{ headerShown: false }}>
            <Stack.Screen name="(auth)" options={{ headerShown: false }} />
            <Stack.Screen name="(app)" options={{ headerShown: false }} />
          </Stack>
        </AuthProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
