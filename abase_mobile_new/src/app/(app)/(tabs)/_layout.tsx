'use client';
import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { View } from 'react-native';
import { Tabs, useFocusEffect } from 'expo-router';
import { Home, CreditCard, Gift, TrendingUp, User } from 'lucide-react-native';
import { useAuth } from '@/context/AuthContext';
import { getCadastroStatus } from '@/services/api/cadastroService';
import { getHomeIssues } from '@/services/api/homeService';
import StatusBanners from '@/components/StatusBanners';

type TabName = 'index' | 'mensalidades' | 'beneficios' | 'antecipacao' | 'perfil';

type ExtendedStatus = {
  basic_complete?: boolean;
  complete?: boolean;
  status?: string;
  exists?: boolean;
  auxilio1_status?: string;
  auxilio2_status?: string;
  cadastro?: { auxilio1_status?: string; auxilio2_status?: string };
  permissions?: { auxilio1?: boolean | 'allowed'; auxilio2?: boolean | 'allowed' };
  auxilios?: { auxilio1?: { allowed?: boolean }; auxilio2?: { allowed?: boolean } };
};

const norm = (s?: string | null) =>
  (s ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

const isPendingStatus = (s?: string | null) => {
  const t = norm(s);
  return (
    t.includes('pendente') || t.includes('em analise') || t.includes('aguard') ||
    t.includes('process') || t.includes('receb') || t.includes('sem contrato')
  );
};

export default function TabsLayout() {
  const { token, roles } = useAuth();
  const [activeTab, setActiveTab] = useState<TabName>('index');
  const [needsCompletion, setNeedsCompletion] = useState(false);
  const [inAnalysis, setInAnalysis] = useState(false);
  const [loadingFlag, setLoadingFlag] = useState(true);
  const [auxilio1Allowed, setAuxilio1Allowed] = useState(false);
  const [auxilio2Allowed, setAuxilio2Allowed] = useState(false);

  const isAssociadoDois = useMemo(
    () => (roles || []).map(r => String(r || '').toLowerCase()).includes('associadodois'),
    [roles],
  );

  const fetchStatus = useCallback(async () => {
    if (!token || !isAssociadoDois) {
      setNeedsCompletion(false);
      setInAnalysis(false);
      setLoadingFlag(false);
      return;
    }
    try {
      setLoadingFlag(true);
      const st = (await getCadastroStatus()) as ExtendedStatus;
      const issues = await getHomeIssues().catch(() => ({ hasOpenIssues: false }));
      const hasIssues = !!issues?.hasOpenIssues;

      const hasBasic =
        st.basic_complete === true ? true : st.basic_complete === undefined ? !!st.exists : false;
      const allowApp = st.complete === true && !isPendingStatus(st.status);

      const str = (v: any) => String(v ?? '').toLowerCase().trim();
      let a1 =
        st?.permissions?.auxilio1 === true ||
        str(st?.permissions?.auxilio1) === 'allowed' ||
        st?.auxilios?.auxilio1?.allowed === true ||
        str(st?.auxilio1_status) === 'liberado' ||
        str(st?.cadastro?.auxilio1_status) === 'liberado';
      let a2 =
        st?.permissions?.auxilio2 === true ||
        str(st?.permissions?.auxilio2) === 'allowed' ||
        st?.auxilios?.auxilio2?.allowed === true ||
        str(st?.auxilio2_status) === 'liberado' ||
        str(st?.cadastro?.auxilio2_status) === 'liberado';

      setNeedsCompletion(!hasBasic);
      setInAnalysis(hasBasic && !allowApp && !(a1 || a2) && !hasIssues);
      setAuxilio1Allowed(!!a1);
      setAuxilio2Allowed(!!a2);
    } catch {
      setNeedsCompletion(true);
      setInAnalysis(false);
      setAuxilio1Allowed(false);
      setAuxilio2Allowed(false);
    } finally {
      setLoadingFlag(false);
    }
  }, [token, isAssociadoDois]);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  useFocusEffect(useCallback(() => { fetchStatus(); }, [fetchStatus]));

  const hideOnProfile = activeTab === 'perfil';

  return (
    <View style={{ flex: 1 }}>
      <Tabs
        screenOptions={({ route }) => ({
          headerShown: false,
          tabBarActiveTintColor: '#f472b6',
          tabBarInactiveTintColor: '#94a3b8',
          tabBarStyle: { backgroundColor: '#0b1222', borderTopColor: '#1f2937' },
          tabBarLabelStyle: { fontSize: 12 },
          tabBarIcon: ({ color, size }) => {
            const icons: Record<string, React.FC<any>> = {
              index: Home,
              mensalidades: CreditCard,
              beneficios: Gift,
              antecipacao: TrendingUp,
              perfil: User,
            };
            const Icon = icons[route.name];
            return Icon ? <Icon size={size} color={color} /> : null;
          },
        })}
        screenListeners={{
          tabPress: (e) => {
            const name = (e.target as string)?.split('-')[0];
            if (name) setActiveTab(name as TabName);
          },
        }}
      >
        <Tabs.Screen
          name="index"
          options={{ tabBarLabel: 'Início' }}
          // Passa as flags como initialParams para que HomeScreen possa consumi-las
        />
        <Tabs.Screen name="mensalidades" options={{ tabBarLabel: 'Mensalida…' }} />
        <Tabs.Screen name="beneficios" options={{ tabBarLabel: 'Benefícios' }} />
        <Tabs.Screen name="antecipacao" options={{ tabBarLabel: 'Antecipação' }} />
        <Tabs.Screen name="perfil" options={{ tabBarLabel: 'Perfil' }} />
      </Tabs>

      <StatusBanners
        needsCompletion={needsCompletion}
        inAnalysis={inAnalysis}
        loadingFlag={loadingFlag}
        hideOnProfile={hideOnProfile}
      />
    </View>
  );
}
