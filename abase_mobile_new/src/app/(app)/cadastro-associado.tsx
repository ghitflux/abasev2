import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert, Animated, Easing, FlatList, Keyboard, KeyboardAvoidingView, Linking, Modal,
  Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { useAuth } from '@/context/AuthContext';
import {
  checkCpfDuplicadoBasico,
  submitCadastroAssociadoBasico,
  submitReuploadBasico,
  getIssuesMy,
  getCadastroShowMy,
  type CadastroAssociadoPayload,
  type MaritalStatus,
} from '@/services/api/cadastroService';
import type { LocalFile } from '@/types';

const COLORS = {
  BG: '#692E44',
  PANEL: '#692E44',
  INPUT_BG: '#FFFFFF',
  INPUT_TEXT: '#111111',
  PLACEHOLDER: '#6b7280',
  LABEL: '#FDFCFD',
  BORDER_PANEL: '#FFFFFF',
  BORDER_FIELD: 'rgba(105,46,68,0.35)',
  BRAND: '#FDFCFD',
  BTN_BG: '#FDFCFD',
  BTN_TEXT: '#692E44',
};
const { BG, PANEL, INPUT_BG, INPUT_TEXT, PLACEHOLDER, LABEL, BORDER_PANEL, BORDER_FIELD, BRAND, BTN_BG, BTN_TEXT } = COLORS;

const MAX_FILE_BYTES = 10 * 1024 * 1024;

const onlyDigits = (s: string) => (s || '').replace(/\D+/g, '');

const maskCPF = (v: string) => {
  const d = onlyDigits(v).slice(0, 11);
  return d.replace(/^(\d{3})(\d)/, '$1.$2').replace(/^(\d{3})\.(\d{3})(\d)/, '$1.$2.$3').replace(/\.(\d{3})(\d)/, '.$1-$2');
};

const maskCNPJ = (v: string) => {
  const d = onlyDigits(v).slice(0, 14);
  return d.replace(/^(\d{2})(\d)/, '$1.$2').replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3').replace(/\.(\d{3})(\d)/, '.$1/$2').replace(/(\d{4})(\d)/, '$1-$2');
};

const maskCEP = (v: string) => {
  const d = onlyDigits(v).slice(0, 8);
  return d.length > 5 ? d.slice(0, 5) + '-' + d.slice(5) : d;
};

const maskDateBR = (v: string) => {
  const d = onlyDigits(v).slice(0, 8);
  if (d.length <= 2) return d;
  if (d.length <= 4) return d.slice(0, 2) + '/' + d.slice(2);
  return d.slice(0, 2) + '/' + d.slice(2, 4) + '/' + d.slice(4, 8);
};

const maskPhoneBR = (v: string) => {
  const d = onlyDigits(v).slice(0, 11);
  if (!d.length) return '';
  if (d.length <= 2) return '(' + d;
  if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
  if (d.length <= 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
  return `(${d.slice(0, 2)}) ${d.slice(2, 3)} ${d.slice(3, 7)}-${d.slice(7, 11)}`;
};

type UF = '' | 'AC' | 'AL' | 'AP' | 'AM' | 'BA' | 'CE' | 'DF' | 'ES' | 'GO' | 'MA' | 'MT'
  | 'MS' | 'MG' | 'PA' | 'PB' | 'PR' | 'PE' | 'PI' | 'RJ' | 'RN' | 'RS' | 'RO'
  | 'RR' | 'SC' | 'SP' | 'SE' | 'TO';

type BasicDocKey = 'cpf_frente' | 'cpf_verso' | 'comp_endereco' | 'contracheque_atual';
const docLabels: Record<BasicDocKey, string> = {
  cpf_frente: 'CPF (frente)',
  cpf_verso: 'CPF (verso)',
  comp_endereco: 'Comprovante de Endereço',
  contracheque_atual: 'Contra-cheque (último mês)',
};

type IssueRow = {
  id?: number;
  title?: string;
  message?: string;
  status?: string;
  required_docs?: string[];
};

const ESTADOS_CIVIS = [
  { label: 'Solteiro(a)', value: 'SOLTEIRO' as const },
  { label: 'Casado(a)', value: 'CASADO' as const },
  { label: 'Separado(a)', value: 'SEPARADO' as const },
  { label: 'Divorciado(a)', value: 'DIVORCIADO' as const },
  { label: 'Viúvo(a)', value: 'VIUVO' as const },
  { label: 'União Estável', value: 'UNIAO_ESTAVEL' as const },
];

const SITUACOES_SERVIDOR = [
  { label: 'Efetivo', value: 'Efetivo' },
  { label: 'Comissionado', value: 'Comissionado' },
  { label: 'Contratado', value: 'Contratado' },
  { label: 'Ativo', value: 'Ativo' },
  { label: 'Aposentado', value: 'Aposentado' },
  { label: 'Pensionista', value: 'Pensionista' },
] as const;

type SelectOption<T extends string = string> = { label: string; value: T };

function SelectField<T extends string>({
  label, value, placeholder = 'Selecione', options, onChange,
}: {
  label: string; value: T | ''; placeholder?: string;
  options: SelectOption<T>[]; onChange: (v: T) => void;
}) {
  const [open, setOpen] = useState(false);
  const selected = options.find(o => o.value === value);
  return (
    <View style={{ flex: 1 }}>
      <Text style={s.label}>{label}</Text>
      <Pressable style={s.pickerWrap} onPress={() => setOpen(true)}>
        <Text style={[s.pickerValue, !selected && { color: PLACEHOLDER }]}>
          {selected ? selected.label : placeholder}
        </Text>
        <Text style={s.chevron}>▾</Text>
      </Pressable>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={s.modalOverlay} onPress={() => setOpen(false)}>
          <View style={s.modalCard}>
            <Text style={s.modalTitle}>{label}</Text>
            <FlatList
              data={options}
              keyExtractor={i => String(i.value)}
              renderItem={({ item }) => (
                <Pressable
                  style={[s.optRow, item.value === value && { borderColor: BG }]}
                  onPress={() => { onChange(item.value as T); setOpen(false); }}
                >
                  <Text style={s.optText}>{item.label}</Text>
                </Pressable>
              )}
            />
            <TouchableOpacity style={s.cancelBtn} onPress={() => setOpen(false)}>
              <Text style={s.cancelTxt}>Cancelar</Text>
            </TouchableOpacity>
          </View>
        </Pressable>
      </Modal>
    </View>
  );
}

const UF_OPTIONS: SelectOption<UF>[] = [
  'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO',
].map(u => ({ label: u, value: u as UF }));

export default function CadastroAssociadoScreen() {
  const router = useRouter();
  const { token, user } = useAuth();

  const [panelWidth, setPanelWidth] = useState(0);
  const shimmerX = useRef(new Animated.Value(-200)).current;
  useEffect(() => {
    if (panelWidth <= 0) return;
    shimmerX.setValue(-200);
    Animated.loop(
      Animated.sequence([
        Animated.timing(shimmerX, {
          toValue: panelWidth + 200, duration: 1800,
          easing: Easing.inOut(Easing.linear), useNativeDriver: true,
        }),
        Animated.timing(shimmerX, { toValue: -200, duration: 0, useNativeDriver: true }),
      ])
    ).start();
  }, [panelWidth, shimmerX]);

  const [docType, setDocType] = useState<'CPF' | 'CNPJ'>('CPF');
  const [cpfCnpj, setCpfCnpj] = useState('');
  const [cpfDupMsg, setCpfDupMsg] = useState<string | null>(null);
  const [checkingCPF, setCheckingCPF] = useState(false);
  const cpfTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [fullName, setFullName] = useState(user?.name ? String(user.name).toUpperCase() : '');
  const [birthDate, setBirthDate] = useState('');
  const [profession, setProfession] = useState('');
  const [maritalStatus, setMaritalStatus] = useState<MaritalStatus>('');
  const [rg, setRg] = useState('');
  const [orgaoExpedidor, setOrgaoExpedidor] = useState('');
  const [cep, setCep] = useState('');
  const [address, setAddress] = useState('');
  const [addressNumber, setAddressNumber] = useState('');
  const [complement, setComplement] = useState('');
  const [neighborhood, setNeighborhood] = useState('');
  const [city, setCity] = useState('');
  const [uf, setUf] = useState<UF>('');
  const [cellphone, setCellphone] = useState('');
  const [orgaoPublico, setOrgaoPublico] = useState('');
  const [situacaoServidor, setSituacaoServidor] = useState<string>('');
  const [matriculaServidorPublico, setMatriculaServidorPublico] = useState('');
  const [email, setEmail] = useState(user?.email || '');
  const [bankName, setBankName] = useState('');
  const [bankAgency, setBankAgency] = useState('');
  const [bankAccount, setBankAccount] = useState('');
  const [accountType, setAccountType] = useState<'' | 'corrente' | 'poupanca'>('');
  const [pixKey, setPixKey] = useState('');
  const [docs, setDocs] = useState<Partial<Record<BasicDocKey, LocalFile | null>>>({});
  const [busy, setBusy] = useState(false);
  const [openIssue, setOpenIssue] = useState<IssueRow | null>(null);

  function pick<T = any>(obj: any, ...keys: string[]): T | undefined {
    for (const k of keys) { if (obj && obj[k] != null) return obj[k] as T; }
    return undefined;
  }

  const loadIssueAndCadastro = useCallback(async () => {
    if (!token) return;
    try {
      const issuesRes = await getIssuesMy();
      const list = Array.isArray(issuesRes?.issues) ? issuesRes.issues : (Array.isArray(issuesRes) ? issuesRes : []);
      const firstOpen = list.find((i: any) =>
        ['open', 'waiting_user', 'received', 'rejected'].includes(String(i.status || '').toLowerCase())
      ) || list[0] || null;
      setOpenIssue(firstOpen ?? null);

      const cadRes = await getCadastroShowMy();
      const cad = cadRes?.cadastro || cadRes?.data || cadRes || null;
      if (cad) {
        const rawDocType = (pick<string>(cad, 'doc_type', 'docType') || 'CPF').toUpperCase();
        setDocType(rawDocType === 'CNPJ' ? 'CNPJ' : 'CPF');
        setCpfCnpj(pick<string>(cad, 'cpf_cnpj', 'cpfCnpj') || '');
        setFullName((pick<string>(cad, 'full_name', 'fullName') || fullName).toUpperCase());
        setBirthDate(pick<string>(cad, 'birth_date', 'birthDate') || '');
        setRg(pick<string>(cad, 'rg') || '');
        setOrgaoExpedidor(pick<string>(cad, 'orgao_expedidor', 'orgaoExpedidor') || '');
        setProfession((pick<string>(cad, 'profession') || '').toUpperCase());
        setMaritalStatus((pick<string>(cad, 'marital_status', 'maritalStatus') as MaritalStatus) || '');
        setCep(pick<string>(cad, 'cep') || '');
        setAddress((pick<string>(cad, 'address', 'logradouro') || '').toUpperCase());
        setAddressNumber(pick<string>(cad, 'address_number', 'numero', 'addressNumber') || '');
        setComplement((pick<string>(cad, 'complement', 'complemento') || '').toUpperCase());
        setNeighborhood((pick<string>(cad, 'neighborhood', 'bairro') || '').toUpperCase());
        setCity((pick<string>(cad, 'city', 'cidade') || '').toUpperCase());
        setUf((pick<string>(cad, 'uf') as UF) || '');
        setCellphone(pick<string>(cad, 'cellphone') || '');
        setEmail(pick<string>(cad, 'email') || email);
        setOrgaoPublico((pick<string>(cad, 'orgao_publico', 'orgaoPublico') || '').toUpperCase());
        setSituacaoServidor(pick<string>(cad, 'situacao_servidor', 'situacaoServidor') || '');
        setMatriculaServidorPublico((pick<string>(cad, 'matricula_servidor_publico', 'matriculaServidorPublico', 'matricula_orgao') || '').toUpperCase());
        setBankName((pick<string>(cad, 'bank_name', 'banco') || '').toUpperCase());
        setBankAgency(pick<string>(cad, 'bank_agency', 'agencia') || '');
        setBankAccount(pick<string>(cad, 'bank_account', 'conta') || '');
        setAccountType((pick<string>(cad, 'account_type', 'tipo_conta') as any) || '');
        setPixKey(pick<string>(cad, 'pix_key', 'chave_pix') || '');
      }
    } catch (e: any) {
      console.log('loadIssueAndCadastro error:', e?.message || e);
    }
  }, [token]);

  useEffect(() => { loadIssueAndCadastro(); }, [loadIssueAndCadastro]);
  useEffect(() => () => { if (cpfTimer.current) clearTimeout(cpfTimer.current); }, []);

  async function tryFillFromCep(raw: string) {
    const d = onlyDigits(raw);
    if (d.length !== 8) return;
    try {
      const r = await fetch(`https://viacep.com.br/ws/${d}/json/`);
      const j = await r.json();
      if (!j || j.erro) return;
      setAddress((j.logradouro || '').toUpperCase());
      setNeighborhood((j.bairro || '').toUpperCase());
      setCity((j.localidade || '').toUpperCase());
      setUf((j.uf || '') as UF);
    } catch { /* noop */ }
  }

  function onChangeCpfCnpj(t: string) {
    setCpfCnpj(t);
    setCpfDupMsg(null);
    const digits = onlyDigits(t);
    if (docType === 'CPF' && digits.length === 11) {
      if (cpfTimer.current) clearTimeout(cpfTimer.current);
      cpfTimer.current = setTimeout(async () => {
        try {
          setCheckingCPF(true);
          const r = await checkCpfDuplicadoBasico(digits);
          setCpfDupMsg(r.exists ? 'CPF já cadastrado. Entre em contato com o suporte.' : null);
        } catch { /* noop */ } finally {
          setCheckingCPF(false);
        }
      }, 400);
    }
  }

  const sanitizeName = (name?: string | null, fallback = 'arquivo') => {
    const base = (name ?? fallback).replace(/[^\w\-.]+/g, '_');
    return base.length ? base : fallback;
  };

  const setDoc = (slot: BasicDocKey, file: LocalFile | null) =>
    setDocs(prev => ({ ...prev, [slot]: file }));

  async function pickFromGallery(slot: BasicDocKey) {
    try {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permissão negada', 'Acesso à galeria é necessário.'); return;
      }
      const res = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: false,
        quality: 0.8,
      });
      if (res.canceled) return;
      const a = res.assets[0];
      if (!a?.uri) { Alert.alert('Galeria', 'Nenhuma imagem selecionada.'); return; }
      if (a.fileSize && a.fileSize > MAX_FILE_BYTES) {
        Alert.alert('Arquivo muito grande', 'Limite por arquivo é 10MB.'); return;
      }
      setDoc(slot, {
        uri: a.uri,
        name: sanitizeName(a.fileName ?? undefined, `${slot}.jpg`),
        type: a.mimeType ?? 'image/jpeg',
        size: a.fileSize ?? undefined,
      });
    } catch {
      Alert.alert('Galeria', 'Não foi possível abrir a galeria.');
    }
  }

  async function handleSubmit() {
    if (busy) return;
    const digits = onlyDigits(cpfCnpj);
    if (docType === 'CPF' && digits.length !== 11) { Alert.alert('Atenção', 'CPF inválido.'); return; }
    if (docType === 'CNPJ' && digits.length !== 14) { Alert.alert('Atenção', 'CNPJ inválido.'); return; }
    if (!fullName.trim()) { Alert.alert('Atenção', 'Informe seu nome completo.'); return; }
    if (onlyDigits(birthDate).length !== 8) { Alert.alert('Atenção', 'Informe a data de nascimento (dd/mm/aaaa).'); return; }
    if (onlyDigits(cep).length !== 8) { Alert.alert('Atenção', 'Informe um CEP válido.'); return; }
    if (!address.trim() || !city.trim() || !uf) { Alert.alert('Atenção', 'Informe logradouro, cidade e UF.'); return; }

    const payload: CadastroAssociadoPayload = {
      docType,
      cpfCnpj: digits,
      fullName: fullName.toUpperCase(),
      birthDate,
      profession: (profession || '').toUpperCase() || undefined,
      maritalStatus: (maritalStatus || '') as MaritalStatus,
      rg,
      orgaoExpedidor,
      cep: onlyDigits(cep),
      logradouro: address.toUpperCase(),
      numero: addressNumber,
      complemento: (complement || '').toUpperCase(),
      bairro: (neighborhood || '').toUpperCase(),
      cidade: city.toUpperCase(),
      uf,
      cellphone: onlyDigits(cellphone),
      orgaoPublico: (orgaoPublico || '').toUpperCase(),
      situacaoServidor: situacaoServidor || undefined,
      matriculaOrgao: (matriculaServidorPublico || '').toUpperCase(),
      email,
      banco: (bankName || '').toUpperCase() || undefined,
      agencia: bankAgency || undefined,
      conta: bankAccount || undefined,
      tipoConta: (accountType || undefined) as any,
      chavePix: pixKey || undefined,
    };

    // collect files
    const fileMap: Record<string, LocalFile> = {};
    (Object.keys(docs) as BasicDocKey[]).forEach(k => {
      const f = docs[k];
      if (f?.uri) fileMap[k] = f;
    });
    const hasFiles = Object.keys(fileMap).length > 0;

    try {
      setBusy(true);
      // Step 1: save basic data
      await submitCadastroAssociadoBasico(payload);

      // Step 2: send files via reuploads if any
      if (hasFiles) {
        const re = await submitReuploadBasico(fileMap);
        Alert.alert('Pronto!', `Dados salvos. Reenvio: ${re?.saved_count ?? 0} arquivo(s).`, [
          { text: 'OK', onPress: () => router.back() },
        ]);
      } else {
        Alert.alert('Pronto!', 'Dados salvos com sucesso.', [
          { text: 'OK', onPress: () => router.back() },
        ]);
      }
    } catch (e: any) {
      Alert.alert('Erro', e?.message || 'Não foi possível salvar.');
    } finally {
      setBusy(false);
    }
  }

  const maskedDoc = docType === 'CPF' ? maskCPF(cpfCnpj) : maskCNPJ(cpfCnpj);

  return (
    <KeyboardAvoidingView style={s.screen} behavior={Platform.select({ ios: 'padding', android: 'height' })}>
      <ScrollView
        keyboardDismissMode={Platform.select({ ios: 'interactive', android: 'on-drag' })}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ padding: 18 }}
      >
        <Pressable onPress={Keyboard.dismiss}>
          <View style={s.panel} onLayout={e => setPanelWidth(e.nativeEvent.layout.width)}>
            <Animated.View
              pointerEvents="none"
              style={[s.shimmer, { transform: [{ translateX: shimmerX }, { rotate: '16deg' }] }]}
            />

            <View style={s.headerWrap}>
              <Text style={s.brand}>ABASE</Text>
            </View>
            <Text style={s.title}>Cadastro do Associado</Text>
            <Text style={s.subtitle}>
              Preencha seus dados pessoais, endereço, contato e bancário.
              Você também pode anexar os 4 documentos essenciais.
            </Text>

            {/* Pendência aberta */}
            {!!openIssue && (
              <View style={s.issueCard}>
                <Text style={s.issueTitle}>Pendência aberta</Text>
                {!!openIssue.title && (
                  <Text style={s.issueLine}><Text style={s.issueLabel}>Título: </Text>{openIssue.title}</Text>
                )}
                {!!openIssue.message && (
                  <Text style={s.issueLine}><Text style={s.issueLabel}>Mensagem: </Text>{openIssue.message}</Text>
                )}
                {!!openIssue.required_docs?.length && (
                  <Text style={s.issueLine}>
                    <Text style={s.issueLabel}>Documentos requeridos: </Text>
                    {openIssue.required_docs.join(', ')}
                  </Text>
                )}
              </View>
            )}

            {/* Documento */}
            <View style={s.section}>
              <Text style={s.sectionTitle}>Documento</Text>
              <View style={s.row}>
                <View style={[s.col, { flex: 0.52 }]}>
                  <SelectField
                    label="Tipo"
                    value={docType}
                    options={[{ label: 'CPF', value: 'CPF' }, { label: 'CNPJ', value: 'CNPJ' }]}
                    onChange={v => { setDocType(v); setCpfDupMsg(null); }}
                  />
                </View>
                <View style={[s.col, { flex: 0.48 }]}>
                  <Text style={s.label}>{docType}</Text>
                  <TextInput
                    style={s.input}
                    keyboardType="number-pad"
                    value={maskedDoc}
                    onChangeText={onChangeCpfCnpj}
                    placeholder={docType === 'CPF' ? '000.000.000-00' : '00.000.000/0000-00'}
                    placeholderTextColor={PLACEHOLDER}
                  />
                </View>
              </View>
              {(!!cpfDupMsg || checkingCPF) && docType === 'CPF' && (
                <Text style={s.warnText}>{checkingCPF ? 'Verificando CPF…' : cpfDupMsg}</Text>
              )}

              <View style={s.row}>
                <View style={[s.col, { flex: 0.6 }]}>
                  <Text style={s.label}>Nome completo</Text>
                  <TextInput
                    style={s.input}
                    value={fullName}
                    onChangeText={t => setFullName(t.toUpperCase())}
                    placeholder="SEU NOME"
                    placeholderTextColor={PLACEHOLDER}
                    autoCapitalize="characters"
                  />
                </View>
                <View style={[s.col, { flex: 0.4 }]}>
                  <Text style={s.label}>Data de nascimento</Text>
                  <TextInput
                    style={s.input}
                    value={maskDateBR(birthDate)}
                    onChangeText={t => setBirthDate(maskDateBR(t))}
                    placeholder="dd/mm/aaaa"
                    keyboardType="number-pad"
                    placeholderTextColor={PLACEHOLDER}
                  />
                </View>
              </View>

              <View style={s.row}>
                <View style={[s.col, { flex: 0.6 }]}>
                  <Text style={s.label}>Profissão (opcional)</Text>
                  <TextInput
                    style={s.input}
                    value={profession}
                    onChangeText={t => setProfession(t.toUpperCase())}
                    placeholder="PROFISSÃO"
                    placeholderTextColor={PLACEHOLDER}
                    autoCapitalize="characters"
                  />
                </View>
                <View style={[s.col, { flex: 0.4 }]}>
                  <SelectField
                    label="Estado civil"
                    value={maritalStatus}
                    options={ESTADOS_CIVIS.map(o => ({ ...o }))}
                    onChange={v => setMaritalStatus(v as MaritalStatus)}
                  />
                </View>
              </View>

              <View style={s.row}>
                <View style={s.col}>
                  <Text style={s.label}>RG (opcional)</Text>
                  <TextInput style={s.input} value={rg} onChangeText={setRg} placeholderTextColor={PLACEHOLDER} />
                </View>
                <View style={s.col}>
                  <Text style={s.label}>Órgão expedidor (opcional)</Text>
                  <TextInput style={s.input} value={orgaoExpedidor} onChangeText={setOrgaoExpedidor} placeholder="SSP/UF" placeholderTextColor={PLACEHOLDER} />
                </View>
              </View>
            </View>

            {/* Endereço */}
            <View style={s.section}>
              <Text style={s.sectionTitle}>Endereço</Text>
              <View style={s.row}>
                <View style={s.col}>
                  <Text style={s.label}>CEP</Text>
                  <TextInput
                    style={s.input} keyboardType="number-pad"
                    value={maskCEP(cep)} onChangeText={v => { setCep(v); tryFillFromCep(v); }}
                    placeholder="00000-000" placeholderTextColor={PLACEHOLDER}
                  />
                </View>
                <View style={{ flex: 1.5 }}>
                  <Text style={s.label}>Logradouro</Text>
                  <TextInput style={s.input} value={address} onChangeText={v => setAddress(v.toUpperCase())} placeholderTextColor={PLACEHOLDER} />
                </View>
              </View>
              <View style={s.row}>
                <View style={[s.col, { flex: 0.6 }]}>
                  <Text style={s.label}>Número (opcional)</Text>
                  <TextInput style={s.input} value={addressNumber} onChangeText={setAddressNumber} placeholder="Nº" placeholderTextColor={PLACEHOLDER} />
                </View>
                <View style={s.col}>
                  <Text style={s.label}>Complemento (opcional)</Text>
                  <TextInput style={s.input} value={complement} onChangeText={v => setComplement(v.toUpperCase())} placeholder="APT, BLOCO..." placeholderTextColor={PLACEHOLDER} />
                </View>
              </View>
              <View style={s.row}>
                <View style={s.col}>
                  <Text style={s.label}>Bairro (opcional)</Text>
                  <TextInput style={s.input} value={neighborhood} onChangeText={v => setNeighborhood(v.toUpperCase())} placeholderTextColor={PLACEHOLDER} />
                </View>
                <View style={s.col}>
                  <Text style={s.label}>Cidade</Text>
                  <TextInput style={s.input} value={city} onChangeText={v => setCity(v.toUpperCase())} placeholderTextColor={PLACEHOLDER} />
                </View>
              </View>
              <SelectField label="UF" value={uf} options={UF_OPTIONS} onChange={setUf} />
            </View>

            {/* Contato & vínculo */}
            <View style={s.section}>
              <Text style={s.sectionTitle}>Contato & vínculo</Text>
              <View style={s.row}>
                <View style={s.col}>
                  <Text style={s.label}>Celular (opcional)</Text>
                  <TextInput
                    style={s.input} keyboardType="number-pad"
                    value={maskPhoneBR(cellphone)} onChangeText={setCellphone}
                    placeholder="(00) 9 0000-0000" placeholderTextColor={PLACEHOLDER}
                  />
                </View>
                <View style={s.col}>
                  <Text style={s.label}>E-mail</Text>
                  <TextInput style={s.input} autoCapitalize="none" keyboardType="email-address" value={email} onChangeText={setEmail} placeholderTextColor={PLACEHOLDER} />
                </View>
              </View>
              <Text style={s.label}>Órgão público (opcional)</Text>
              <TextInput style={s.input} value={orgaoPublico} onChangeText={v => setOrgaoPublico(v.toUpperCase())} placeholderTextColor={PLACEHOLDER} />
              <View style={s.row}>
                <SelectField
                  label="Situação do servidor"
                  value={situacaoServidor}
                  options={SITUACOES_SERVIDOR.map(o => ({ ...o }))}
                  onChange={setSituacaoServidor}
                />
                <View style={s.col}>
                  <Text style={s.label}>Matrícula (opcional)</Text>
                  <TextInput style={s.input} value={matriculaServidorPublico} onChangeText={v => setMatriculaServidorPublico(v.toUpperCase())} placeholderTextColor={PLACEHOLDER} />
                </View>
              </View>
            </View>

            {/* Dados bancários */}
            <View style={s.section}>
              <Text style={s.sectionTitle}>Dados bancários</Text>
              <View style={s.row}>
                <View style={{ flex: 1.5 }}>
                  <Text style={s.label}>Banco (opcional)</Text>
                  <TextInput style={s.input} value={bankName} onChangeText={v => setBankName(v.toUpperCase())} placeholder="BANCO" placeholderTextColor={PLACEHOLDER} />
                </View>
                <View style={[s.col, { flex: 0.8 }]}>
                  <Text style={s.label}>Agência</Text>
                  <TextInput style={s.input} keyboardType="number-pad" value={bankAgency} onChangeText={setBankAgency} placeholder="0000" placeholderTextColor={PLACEHOLDER} />
                </View>
              </View>
              <View style={s.row}>
                <View style={s.col}>
                  <Text style={s.label}>Conta</Text>
                  <TextInput style={s.input} keyboardType="number-pad" value={bankAccount} onChangeText={setBankAccount} placeholder="00000-0" placeholderTextColor={PLACEHOLDER} />
                </View>
                <SelectField
                  label="Tipo de conta"
                  value={accountType}
                  options={[{ label: 'Corrente', value: 'corrente' }, { label: 'Poupança', value: 'poupanca' }]}
                  onChange={v => setAccountType(v as any)}
                />
              </View>
              <Text style={s.label}>Chave PIX (opcional)</Text>
              <TextInput style={s.input} value={pixKey} onChangeText={setPixKey} placeholder="CPF / E-mail / Telefone" placeholderTextColor={PLACEHOLDER} />
            </View>

            {/* Documentos */}
            <View style={s.section}>
              <Text style={s.sectionTitle}>Documentos (opcional)</Text>
              {(Object.keys(docLabels) as BasicDocKey[]).map(slot => {
                const f = docs[slot] || null;
                const required = Array.isArray(openIssue?.required_docs) && (openIssue?.required_docs as string[]).includes(slot);
                return (
                  <View key={slot} style={s.docCard}>
                    <Text style={s.docTitle}>
                      {docLabels[slot]}
                      {required ? <Text style={s.reqTag}> • requerido</Text> : null}
                    </Text>
                    <Text style={s.docHint}>Imagens (Galeria) — até 10MB.</Text>
                    {f ? (
                      <View style={{ gap: 8, marginTop: 8 }}>
                        <Text style={s.docFileName} numberOfLines={1}>{f.name}</Text>
                        <View style={s.row}>
                          <TouchableOpacity style={s.smallBtn} onPress={() => Linking.openURL(f.uri).catch(() => {})} activeOpacity={0.85}>
                            <Text style={s.smallBtnTxt}>Ver</Text>
                          </TouchableOpacity>
                          <TouchableOpacity style={s.smallBtn} onPress={() => pickFromGallery(slot)} activeOpacity={0.85}>
                            <Text style={s.smallBtnTxt}>Trocar</Text>
                          </TouchableOpacity>
                          <TouchableOpacity style={[s.smallBtn, { borderColor: '#ef4444' }]} onPress={() => setDoc(slot, null)} activeOpacity={0.85}>
                            <Text style={[s.smallBtnTxt, { color: '#ef4444' }]}>Remover</Text>
                          </TouchableOpacity>
                        </View>
                      </View>
                    ) : (
                      <View style={{ marginTop: 8 }}>
                        <TouchableOpacity style={s.smallBtn} onPress={() => pickFromGallery(slot)} activeOpacity={0.85}>
                          <Text style={s.smallBtnTxt}>Galeria</Text>
                        </TouchableOpacity>
                      </View>
                    )}
                  </View>
                );
              })}
            </View>

            <TouchableOpacity
              style={[s.btnSubmit, busy && { opacity: 0.6 }]}
              onPress={handleSubmit}
              disabled={busy}
              activeOpacity={0.85}
            >
              <Text style={s.btnSubmitTxt}>{busy ? 'Salvando…' : 'Salvar e enviar'}</Text>
            </TouchableOpacity>

            <TouchableOpacity style={s.btnBack} onPress={() => router.back()} activeOpacity={0.85}>
              <Text style={s.btnBackTxt}>Voltar</Text>
            </TouchableOpacity>
          </View>
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: BG },
  panel: { backgroundColor: PANEL, borderRadius: 16, borderWidth: 1, borderColor: BORDER_PANEL, padding: 16, overflow: 'hidden' },
  shimmer: {
    position: 'absolute', top: -20, bottom: -20, width: 60,
    backgroundColor: 'rgba(255,255,255,0.07)', zIndex: 0,
  },
  headerWrap: { alignItems: 'center', marginBottom: 4 },
  brand: { color: BRAND, fontSize: 28, fontWeight: '900', letterSpacing: 6 },
  title: { color: LABEL, fontSize: 16, fontWeight: '800', textAlign: 'center', marginBottom: 4 },
  subtitle: { color: 'rgba(253,252,253,0.75)', fontSize: 12, textAlign: 'center', marginBottom: 12 },
  section: { marginTop: 12 },
  sectionTitle: { color: BRAND, fontWeight: '800', fontSize: 14, marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 },
  issueCard: { backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: 10, padding: 12, marginBottom: 12, borderWidth: 1, borderColor: 'rgba(255,255,255,0.2)' },
  issueTitle: { color: BRAND, fontWeight: '800', marginBottom: 4 },
  issueLine: { color: LABEL, fontSize: 13, marginTop: 2 },
  issueLabel: { fontWeight: '700' },
  row: { flexDirection: 'row', gap: 10, marginBottom: 8 },
  col: { flex: 1 },
  label: { color: LABEL, marginBottom: 4, fontSize: 12 },
  input: {
    backgroundColor: INPUT_BG, borderWidth: 1, borderColor: BORDER_FIELD, borderRadius: 10,
    color: INPUT_TEXT, paddingHorizontal: 12,
    paddingVertical: Platform.select({ ios: 12, android: 10 }) as number,
    marginBottom: 8,
  },
  warnText: { color: '#fef08a', fontSize: 12, marginTop: -4, marginBottom: 8 },
  pickerWrap: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: INPUT_BG, borderWidth: 1, borderColor: BORDER_FIELD, borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: Platform.select({ ios: 12, android: 10 }) as number,
    marginBottom: 8,
  },
  pickerValue: { color: INPUT_TEXT, flex: 1, fontSize: 14 },
  chevron: { color: '#9ca3af', fontSize: 12 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'center', alignItems: 'center', padding: 24 },
  modalCard: { backgroundColor: '#111827', borderRadius: 14, borderWidth: 1, borderColor: 'rgba(255,255,255,0.15)', padding: 16, width: '100%', maxHeight: '80%' },
  modalTitle: { color: '#e5e7eb', fontWeight: '700', fontSize: 16, marginBottom: 12 },
  optRow: { borderWidth: 1, borderColor: 'rgba(255,255,255,0.15)', borderRadius: 10, padding: 12, marginBottom: 8 },
  optText: { color: '#e5e7eb', fontSize: 14 },
  cancelBtn: { marginTop: 8, borderWidth: 1, borderColor: '#ef4444', borderRadius: 10, alignItems: 'center', paddingVertical: 12 },
  cancelTxt: { color: '#ef4444', fontWeight: '700' },
  docCard: { backgroundColor: 'rgba(0,0,0,0.15)', borderRadius: 10, borderWidth: 1, borderColor: 'rgba(255,255,255,0.2)', padding: 12, marginBottom: 10 },
  docTitle: { color: LABEL, fontWeight: '700' },
  docHint: { color: 'rgba(253,252,253,0.6)', fontSize: 12, marginTop: 2 },
  reqTag: { color: '#fbbf24', fontWeight: '700', fontSize: 11 },
  docFileName: { color: 'rgba(253,252,253,0.75)', fontSize: 12 },
  smallBtn: { borderWidth: 1, borderColor: BRAND, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 8 },
  smallBtnTxt: { color: BRAND, fontWeight: '700', fontSize: 13 },
  btnSubmit: { marginTop: 18, height: 50, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: BTN_BG },
  btnSubmitTxt: { color: BTN_TEXT, fontWeight: '900', fontSize: 16 },
  btnBack: { marginTop: 10, borderRadius: 12, borderWidth: 1, borderColor: 'rgba(255,255,255,0.35)', alignItems: 'center', paddingVertical: 13 },
  btnBackTxt: { color: LABEL, fontWeight: '700' },
});
