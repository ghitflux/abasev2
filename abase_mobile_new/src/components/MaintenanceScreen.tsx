import { View, Text, StyleSheet } from 'react-native';

type Props = {
  message: string;
};

export default function MaintenanceScreen({ message }: Props) {
  return (
    <View style={styles.container}>
      <Text style={styles.icon}>🔧</Text>
      <Text style={styles.title}>App em Manutenção</Text>
      <Text style={styles.message}>{message}</Text>
      <Text style={styles.footer}>
        Em caso de dúvidas, entre em contato com a ABASE.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0b1222',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
  },
  icon: {
    fontSize: 56,
    marginBottom: 24,
  },
  title: {
    color: '#f472b6',
    fontSize: 22,
    fontWeight: '700',
    marginBottom: 16,
    textAlign: 'center',
  },
  message: {
    color: '#cbd5e1',
    fontSize: 15,
    textAlign: 'center',
    lineHeight: 24,
    marginBottom: 32,
  },
  footer: {
    color: '#475569',
    fontSize: 13,
    textAlign: 'center',
  },
});
