import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import React from 'react';
import { Text } from 'react-native';

import { useAuth } from '../context/AuthContext';
import AntecipacaoScreen from '../screens/AntecipacaoScreen';
import CadastroAssociadoScreen from '../screens/CadastroAssociadoScreen';
import HomeScreen from '../screens/HomeScreen';
import MensalidadesScreen from '../screens/MensalidadesScreen';
import PendenciasScreen from '../screens/PendenciasScreen';
import PerfilScreen from '../screens/PerfilScreen';

const Tab = createBottomTabNavigator();

function TabIcon({ label, focused }: { label: string; focused: boolean }) {
  return (
    <Text style={{ fontSize: 20, opacity: focused ? 1 : 0.5 }}>{label}</Text>
  );
}

export default function TabNavigator() {
  const { hasRole } = useAuth();
  const isAgente = hasRole('AGENTE', 'ADMIN');
  const isAssociado = hasRole('ASSOCIADO');

  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: '#1B4F9C',
        tabBarInactiveTintColor: '#8A9BB0',
        tabBarStyle: { paddingBottom: 4, height: 60 },
      }}
    >
      <Tab.Screen
        name="Home"
        component={HomeScreen}
        options={{
          tabBarLabel: 'Início',
          tabBarIcon: ({ focused }) => <TabIcon label="🏠" focused={focused} />,
        }}
      />

      {isAssociado && (
        <Tab.Screen
          name="Mensalidades"
          component={MensalidadesScreen}
          options={{
            tabBarLabel: 'Parcelas',
            tabBarIcon: ({ focused }) => <TabIcon label="💰" focused={focused} />,
          }}
        />
      )}

      {isAssociado && (
        <Tab.Screen
          name="Antecipacao"
          component={AntecipacaoScreen}
          options={{
            tabBarLabel: 'Histórico',
            tabBarIcon: ({ focused }) => <TabIcon label="📋" focused={focused} />,
          }}
        />
      )}

      {isAssociado && (
        <Tab.Screen
          name="Pendencias"
          component={PendenciasScreen}
          options={{
            tabBarLabel: 'Pendências',
            tabBarIcon: ({ focused }) => <TabIcon label="📄" focused={focused} />,
          }}
        />
      )}

      {isAgente && (
        <Tab.Screen
          name="Cadastro"
          component={CadastroAssociadoScreen}
          options={{
            tabBarLabel: 'Novo Assoc.',
            tabBarIcon: ({ focused }) => <TabIcon label="➕" focused={focused} />,
          }}
        />
      )}

      <Tab.Screen
        name="Perfil"
        component={PerfilScreen}
        options={{
          tabBarLabel: 'Perfil',
          tabBarIcon: ({ focused }) => <TabIcon label="👤" focused={focused} />,
        }}
      />
    </Tab.Navigator>
  );
}
