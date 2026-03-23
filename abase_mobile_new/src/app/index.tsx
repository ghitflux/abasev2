import { Redirect } from 'expo-router';

// Redireciona para a tela de splash ao iniciar
export default function Root() {
  return <Redirect href="/(auth)/splash" />;
}
