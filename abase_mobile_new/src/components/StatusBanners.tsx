// Banners animados de status do cadastro — migrado de utils/MainTabs.tsx
import React, { useEffect, useRef } from 'react';
import { View, Text, TouchableOpacity, Animated } from 'react-native';
import { useRouter } from 'expo-router';

type Props = {
  needsCompletion: boolean;
  inAnalysis: boolean;
  loadingFlag: boolean;
  hideOnProfile?: boolean;
};

export default function StatusBanners({
  needsCompletion,
  inAnalysis,
  loadingFlag,
  hideOnProfile = false,
}: Props) {
  const router = useRouter();
  const fadeNeed = useRef(new Animated.Value(0)).current;
  const fadeInfo = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const showNeed = needsCompletion && !loadingFlag;
    Animated.timing(fadeNeed, {
      toValue: showNeed ? 1 : 0,
      duration: 280,
      useNativeDriver: true,
    }).start();
  }, [needsCompletion, loadingFlag, fadeNeed]);

  useEffect(() => {
    const showInfo = !needsCompletion && inAnalysis && !loadingFlag;
    Animated.timing(fadeInfo, {
      toValue: showInfo ? 1 : 0,
      duration: 280,
      useNativeDriver: true,
    }).start();
  }, [inAnalysis, needsCompletion, loadingFlag, fadeInfo]);

  const goComplete = () => {
    router.push('/(app)/atualizar-cadastro');
  };

  if (hideOnProfile) return null;

  return (
    <>
      {/* Overlay BLOQUEANTE — "Complete seu cadastro" */}
      <Animated.View
        pointerEvents={needsCompletion ? 'auto' : 'none'}
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 86,
          paddingHorizontal: 16,
          opacity: fadeNeed,
          zIndex: 10,
          elevation: 10,
        }}
      >
        <View
          style={{
            backgroundColor: 'rgba(15,23,42,0.92)',
            borderColor: 'rgba(148,163,184,0.25)',
            borderWidth: 1,
            borderRadius: 16,
            paddingVertical: 12,
            paddingHorizontal: 14,
            shadowColor: '#000',
            shadowOpacity: 0.25,
            shadowRadius: 12,
            shadowOffset: { width: 0, height: 8 },
            gap: 8,
          }}
        >
          <Text style={{ color: '#f8fafc', fontWeight: '800' }}>Complete seu cadastro</Text>
          <Text style={{ color: '#cbd5e1' }}>
            Preencha seus dados básicos para liberar todos os recursos do ABASE.
          </Text>
          <TouchableOpacity
            onPress={goComplete}
            style={{
              alignSelf: 'flex-start',
              backgroundColor: '#22d3ee',
              paddingVertical: 10,
              paddingHorizontal: 14,
              borderRadius: 10,
              marginTop: 2,
            }}
          >
            <Text style={{ color: '#00121a', fontWeight: '900' }}>Completar agora</Text>
          </TouchableOpacity>
        </View>
      </Animated.View>

      {/* Faixa NÃO BLOQUEANTE — "Dados enviados e em análise" */}
      <Animated.View
        pointerEvents="box-none"
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 86,
          paddingHorizontal: 16,
          opacity: fadeInfo,
          zIndex: 9,
          elevation: 9,
        }}
      >
        <View
          pointerEvents="none"
          style={{
            backgroundColor: 'rgba(30,41,59,0.92)',
            borderColor: 'rgba(96,165,250,0.35)',
            borderWidth: 1,
            borderRadius: 16,
            paddingVertical: 10,
            paddingHorizontal: 12,
            flexDirection: 'row',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <Text style={{ color: '#bfdbfe', flex: 1 }}>
            Dados enviados e em análise. Em breve você terá um retorno.
          </Text>
        </View>
      </Animated.View>
    </>
  );
}
