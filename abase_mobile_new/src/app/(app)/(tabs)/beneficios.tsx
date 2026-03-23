import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from 'react-native';
import { Briefcase, Coins, Users, Shield, Award, Info, ChevronUp, ChevronDown } from 'lucide-react-native';

type Benefit = {
  id: string; title: string; subtitle: string;
  Icon: React.ComponentType<any>; iconBg: string;
  badges: string[]; bullets: string[];
};

const benefits: Benefit[] = [
  {
    id: 'juridico',
    title: 'Consultoria Jurídica Especializada',
    subtitle: 'Atendimento jurídico em diversas áreas (criminal, previdenciário, cível, trabalhista).',
    Icon: Briefcase, iconBg: '#3b1f3f',
    badges: ['Consultoria', 'Multidisciplinar', 'Elegível após 1ª mensalidade'],
    bullets: [
      'Orientação inicial e triagem do caso.',
      'Encaminhamento a especialistas por área (ex.: criminal, previdenciário, cível, trabalhista).',
      'Acompanhamento básico de demandas administrativas quando aplicável.',
      'Atendimento remoto e, quando necessário, presencial mediante agenda.',
      'Consultoria sem custo adicional; eventual representação em juízo pode ser orçada à parte.',
    ],
  },
  {
    id: 'financeira',
    title: 'Consultoria Financeira',
    subtitle: 'Redução de taxas e retirada de descontos indevidos em folha de pagamento.',
    Icon: Coins, iconBg: '#1f2933',
    badges: ['Orientação Financeira', 'Planejamento'],
    bullets: [
      'Análise de contracheques e descontos recorrentes.',
      'Identificação de cobranças irregulares ou abusivas.',
      'Orientação sobre renegociação de dívidas e organização financeira pessoal.',
      'Apoio na busca de soluções junto a bancos e financeiras, quando aplicável.',
    ],
  },
  {
    id: 'funerario',
    title: 'Auxílio Funerário',
    subtitle: 'Auxílio de R$ 5.000 (cinco mil reais) em caso de falecimento, elegível após 24 mensalidades concluídas.',
    Icon: Users, iconBg: '#432751',
    badges: ['Benefício Financeiro', 'Elegível após 24 mensalidades'],
    bullets: [
      'Valor do auxílio: R$ 5.000 (cinco mil reais).',
      'Elegibilidade: a partir de 24 mensalidades concluídas.',
      'Concessão mediante apresentação de documentação comprobatória (ex.: certidão de óbito e documentos do(s) beneficiário(s)).',
      'Processo de análise e liberação conforme regulamento interno.',
    ],
  },
  {
    id: 'emergencial',
    title: 'Auxílio Emergencial',
    subtitle: 'Em situações de necessidade urgente, a partir da 3ª mensalidade, mediante comprovação.',
    Icon: Shield, iconBg: '#3b1a26',
    badges: ['Urgência', 'Elegível após 3 mensalidades'],
    bullets: [
      'Disponível a partir da 3ª mensalidade concluída.',
      'Necessária comprovação da necessidade (ex.: documentos).',
      'Análise individual pela diretoria/assistência e definição do suporte cabível.',
      'Condições e valores podem variar conforme cada caso e disponibilidade orçamentária.',
    ],
  },
];

function BenefitCard({ benefit }: { benefit: Benefit }) {
  const [open, setOpen] = useState(true);
  const { Icon } = benefit;

  return (
    <View style={s.card}>
      <TouchableOpacity style={s.headerRow} activeOpacity={0.8} onPress={() => setOpen(v => !v)}>
        <View style={s.iconWrapper}>
          <View style={[s.iconBox, { backgroundColor: benefit.iconBg }]}>
            <Icon size={20} color="#e5e7eb" />
          </View>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={s.itemTitle}>{benefit.title}</Text>
          <Text style={s.subtitle} numberOfLines={open ? 2 : 1}>{benefit.subtitle}</Text>
          <View style={s.badgeRow}>
            {benefit.badges.map((b, i) => (
              <View key={i} style={s.badge}>
                <Text style={s.badgeText}>{b}</Text>
              </View>
            ))}
          </View>
        </View>
        {open ? <ChevronUp size={20} color="#94a3b8" /> : <ChevronDown size={20} color="#94a3b8" />}
      </TouchableOpacity>
      {open && (
        <View style={s.bullets}>
          {benefit.bullets.map((line, i) => (
            <View key={i} style={s.bulletRow}>
              <Text style={s.bulletDot}>{'\u2022'}</Text>
              <Text style={s.bulletText}>{line}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

export default function BeneficiosScreen() {
  return (
    <ScrollView style={s.container} contentContainerStyle={s.content}>
      <Text style={s.title}>Benefícios ABASE</Text>
      <View style={s.banner}>
        <View style={s.bannerIconBox}>
          <Award size={20} color="#e5e7eb" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={s.bannerTitle}>Vantagens para quem serve</Text>
          <Text style={s.bannerDesc}>
            Conheça os benefícios disponíveis aos associados ABASE e como acessar cada um.
          </Text>
        </View>
      </View>
      {benefits.map(b => <BenefitCard key={b.id} benefit={b} />)}
      <View style={s.info}>
        <View style={s.infoHeader}>
          <Info size={18} color="#94a3b8" />
          <Text style={s.infoTitle}>Informações resumidas</Text>
        </View>
        <Text style={s.infoText}>
          A concessão de benefícios segue o regulamento interno e análise documental. Em caso de dúvidas, procure nosso atendimento.
        </Text>
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a' },
  content: { padding: 16, paddingBottom: 32, gap: 14 },
  title: { color: '#e5e7eb', fontSize: 22, fontWeight: '700', marginBottom: 4 },
  banner: { backgroundColor: '#111827', borderRadius: 16, padding: 16, flexDirection: 'row', alignItems: 'center' },
  bannerIconBox: { width: 40, height: 40, borderRadius: 999, marginRight: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: '#7c2d12' },
  bannerTitle: { color: '#e5e7eb', fontWeight: '700', marginBottom: 4 },
  bannerDesc: { color: '#94a3b8', fontSize: 13 },
  card: { backgroundColor: '#111827', borderRadius: 16, padding: 16 },
  headerRow: { flexDirection: 'row', alignItems: 'center' },
  iconWrapper: { marginRight: 12 },
  iconBox: { width: 40, height: 40, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  itemTitle: { color: '#e5e7eb', fontWeight: '700', fontSize: 15, marginBottom: 2 },
  subtitle: { color: '#94a3b8', fontSize: 12 },
  badgeRow: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 12, gap: 8 },
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999, backgroundColor: '#020617', borderWidth: 1, borderColor: 'rgba(148,163,184,0.35)' },
  badgeText: { color: '#e5e7eb', fontSize: 11, fontWeight: '500' },
  bullets: { marginTop: 12 },
  bulletRow: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 4 },
  bulletDot: { color: '#e5e7eb', fontSize: 10, marginRight: 6, marginTop: 3 },
  bulletText: { flex: 1, color: '#e5e7eb', fontSize: 13 },
  info: { backgroundColor: '#0b1020', borderRadius: 14, padding: 16, marginTop: 8 },
  infoHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 6 },
  infoTitle: { marginLeft: 6, color: '#e5e7eb', fontWeight: '600', fontSize: 14 },
  infoText: { color: '#94a3b8', fontSize: 13 },
});
