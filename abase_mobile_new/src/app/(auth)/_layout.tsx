import { Stack } from 'expo-router';

export default function AuthLayout() {
  return (
    <Stack screenOptions={{ headerShown: false, animation: 'fade' }}>
      <Stack.Screen name="splash" />
      <Stack.Screen name="login" />
      <Stack.Screen name="register" />
      <Stack.Screen name="forgot-password" />
      <Stack.Screen
        name="reset-password"
        options={{ headerShown: true, title: 'Redefinir Senha', headerBackTitle: 'Voltar' }}
      />
    </Stack>
  );
}
