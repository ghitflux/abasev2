import { Stack, Redirect } from 'expo-router';
import { View, ActivityIndicator } from 'react-native';
import { useAuth } from '@/context/AuthContext';
import { SafeAreaView } from 'react-native-safe-area-context';

export default function AppLayout() {
  const { token, loadingAuth } = useAuth();

  if (loadingAuth) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0b1222' }}>
        <ActivityIndicator color="#f472b6" size="large" />
      </View>
    );
  }

  if (!token) {
    return <Redirect href="/(auth)/login" />;
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#0b1222' }} edges={['top']}>
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="espera" />
        <Stack.Screen name="cadastro-associado" options={{ animation: 'slide_from_right' }} />
        <Stack.Screen name="atualizar-cadastro" options={{ animation: 'slide_from_right' }} />
        <Stack.Screen name="atualizar-dados-basicos" options={{ animation: 'slide_from_right' }} />
        <Stack.Screen name="pendencias-documentos" options={{ animation: 'slide_from_right' }} />
        <Stack.Screen name="auxilio-emergencial" options={{ animation: 'slide_from_right' }} />
      </Stack>
    </SafeAreaView>
  );
}
