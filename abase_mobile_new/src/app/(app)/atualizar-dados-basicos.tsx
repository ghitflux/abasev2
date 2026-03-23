import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator, Alert, FlatList, Keyboard, KeyboardAvoidingView, Modal,
  Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View,
} from 'react-native';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { useAuth } from '@/context/AuthContext';
import { submitAtualizarBasico } from '@/services/api/atualizarService';
import type { CadastroAssociadoPayload, MaritalStatus } from '@/services/api/cadastroService';
import type { LocalFile } from '@/types';

const BG = '#0c1622';
const CARD = '#102131';
const INK = '#e5eef5';
const MUTED = '#9fb0bf';
const BRAND = '#22d3ee';
const BORDER = 'rgba(148,163,184,.25)';
const INPUT_BG = '#0b1a22';
const PLACEHOLDER = '#9fb0bf';

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
      <Text style={st.label}>{label}</Text>
      <Pressable style={st.selectBox} onPress={() => setOpen(true)}>
        <Text style={[st.selectValue, !selected && { color: PLACEHOLDER }]}>
          {selected ? selected.label : placeholder}
        </Text>
        <Text style={st.chevron}>▾</Text>
      </Pressable>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={st.overlay} onPress={() => setOpen(false)}>
          <View style={st.modalCard}>
            <Text style={st.modalTitle}>{label}</Text>
            <FlatList
              data={options}
              keyExtractor={i => String(i.value)}
              renderItem={({ item }) => (
                <Pressable
                  style={[st.optRow, item.value === value && { borderColor: BRAND }]}
                  onPress={() => { onChange(item.value as T); setOpen(false); }}
                >
                  <Text style={st.optText}>{item.label}</Text>
                </Pressable>
              )}
            />
            <TouchableOpacity style={st.cancelBtn} onPress={() => setOpen(false)}>
              <Text style={st.cancelTxt}>Cancelar</Text>
            </TouchableOpacity>
          </View>
        </Pressable>
      </Modal>
    </View>
  );
}

const DOC_TYPES: SelectOption<'CPF' | 'CNPJ'>[] = [
  { label: 'CPF', value: 'CPF' },
  { label: 'CNPJ', value: 'CNPJ' },
];

const ESTADO_CIVIL: SelectOption<string>[] = [
  { value: 'SOLTEIRO', label: 'Solteiro(a)' },
  { value: 'CASADO', label: 'Casado(a)' },
  { value: 'SEPARADO', label: 'Separado(a)' },
  { value: 'DIVORCIADO', label: 'Divorciado(a)' },
  { value: 'VIUVO', label: 'Viúvo(a)' },
  { value: 'UNIAO_ESTAVEL', label: 'União Estável' },
];

const UF_OPTIONS: SelectOption<UF>[] = [
  'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO',
].map(u => ({ label: u, value: u as UF }));

const SITUACAO_SERVIDOR: SelectOption<string>[] = [
  { value: 'EFETIVO', label: 'Efetivo' },
  { value: 'COMISSIONADO', label: 'Comissionado' },
  { value: 'CONTRATADO', label: 'Contratado' },
  { value: 'ATIVO', label: 'Ativo' },
  { value: 'APOSENTADO', label: 'Aposentado' },
  { value: 'PENSIONISTA', label: 'Pensionista' },
];

const ACCOUNT_TYPES: SelectOption<string>[] = [
  { value: 'corrente', label: 'Conta corrente' },
  { value: 'poupanca', label: 'Conta poupança' },
];

type DocKey = 'cpf_frente' | 'cpf_verso' | 'comp_endereco' | 'contracheque_atual';
const docLabels: Record<DocKey, string> = {
  cpf_frente: 'CPF (frente)',
  cpf_verso: 'CPF (verso)',
  comp_endereco: 'Comprovante de Endereço',
  contracheque_atual: 'Contra-cheque (último mês)',
};

export default function AtualizarDadosBasicosScreen() {
  const router = useRouter();
  const { user } = useAuth();

  const [docType, setDocType] = useState<'CPF' | 'CNPJ'>('CPF');
  const [cpfCnpj, setCpfCnpj] = useState('');
  const [fullName, setFullName] = useState('');
  const [birthDate, setBirthDate] = useState('');
  const [profession, setProfession] = useState('');
  const [marital, setMarital] = useState<string>('');
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
  const [email, setEmail] = useState(user?.email || '');
  const [orgaoPublico, setOrgaoPublico] = useState('');
  const [situacaoServidor, setSituacaoServidor] = useState<string>('');
  const [matricula, setMatricula] = useState('');
  const [bankName, setBankName] = useState('');
  const [bankAgency, setBankAgency] = useState('');
  const [bankAccount, setBankAccount] = useState('');
  const [accountType, setAccountType] = useState<string>('');
  const [pixKey, setPixKey] = useState('');
  const [files, setFiles] = useState<Partial<Record<DocKey, LocalFile | null>>>({});
  const [loadingCEP, setLoadingCEP] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const maskedDoc = useMemo(() => docType === 'CPF' ? maskCPF(cpfCnpj) : maskCNPJ(cpfCnpj), [docType, cpfCnpj]);

  useEffect(() => {
    const d = onlyDigits(cep);
    if (d.length !== 8) return;
    (async () => {
      try {
        setLoadingCEP(true);
        const r = await fetch(`https://viacep.com.br/ws/${d}/json/`);
        const j = await r.json();
        if (!j?.erro) {
          setAddress((j.logradouro ?? '').toString().toUpperCase());
          setNeighborhood((j.bairro ?? '').toString().toUpperCase());
          setCity((j.localidade ?? '').toString().toUpperCase());
          const ufFound = (j.uf ?? '').toString().toUpperCase() as UF;
          if (ufFound) setUf(ufFound);
        }
      } catch { /* noop */ } finally {
        setLoadingCEP(false);
      }
    })();
  }, [cep]);

  const canSubmit = useMemo(() => {
    const docOk = docType === 'CPF' ? onlyDigits(cpfCnpj).length === 11 : onlyDigits(cpfCnpj).length === 14;
    return docOk && fullName.trim().length >= 3 && maskDateBR(birthDate).length === 10
      && onlyDigits(cep).length === 8 && address.trim().length >= 3
      && city.trim().length >= 2 && (uf || '').length === 2 && !submitting;
  }, [docType, cpfCnpj, fullName, birthDate, cep, address, city, uf, submitting]);

  const setFile = (key: DocKey, f: LocalFile | null) => setFiles(prev => ({ ...prev, [key]: f }));

  async function pickFromGallery(key: DocKey) {
    try {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permissão negada', 'Acesso à galeria é necessário.'); return;
      }
      const res = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: false,
        quality: 0.9,
      });
      if (res.canceled) return;
      const a = res.assets[0];
      if (!a?.uri) return;
      if (a.fileSize && a.fileSize > MAX_FILE_BYTES) {
        Alert.alert('Arquivo muito grande', 'Limite por arquivo é 10MB.'); return;
      }
      setFile(key, {
        uri: a.uri,
        name: a.fileName ?? `${key}-${Date.now()}.jpg`,
        type: a.mimeType ?? 'image/jpeg',
        size: a.fileSize ?? undefined,
      });
    } catch {
      Alert.alert('Galeria', 'Não foi possível abrir a galeria.');
    }
  }

  async function submit() {
    if (!canSubmit || submitting) return;
    try {
      setSubmitting(true);
      const payload: CadastroAssociadoPayload = {
        docType,
        cpfCnpj: onlyDigits(cpfCnpj),
        fullName: fullName.toUpperCase(),
        birthDate,
        profession: profession || undefined,
        maritalStatus: (marital || '') as MaritalStatus,
        rg: rg || undefined,
        orgaoExpedidor: orgaoExpedidor || undefined,
        cep: onlyDigits(cep),
        logradouro: address.toUpperCase(),
        numero: addressNumber,
        complemento: complement || undefined,
        bairro: neighborhood ? neighborhood.toUpperCase() : '',
        cidade: city.toUpperCase(),
        uf: uf || '',
        cellphone: onlyDigits(cellphone),
        email: email.trim(),
        orgaoPublico: orgaoPublico ? orgaoPublico.toUpperCase() : '',
        matriculaOrgao: matricula ? matricula.toUpperCase() : '',
        situacaoServidor: situacaoServidor || undefined,
        banco: bankName ? bankName.toUpperCase() : undefined,
        agencia: bankAgency || undefined,
        conta: bankAccount || undefined,
        tipoConta: (accountType || undefined) as any,
        chavePix: pixKey || undefined,
        files: {
          cpf_frente: files.cpf_frente ?? null,
          cpf_verso: files.cpf_verso ?? null,
          comp_endereco: files.comp_endereco ?? null,
          contracheque_atual: files.contracheque_atual ?? null,
        },
      };
      await submitAtualizarBasico(payload);
      Alert.alert('Pronto', 'Dados básicos atualizados.');
    } catch (e: any) {
      Alert.alert('Atenção', e?.message || 'Não foi possível enviar.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <ScrollView style={st.page} contentContainerStyle={{ padding: 16, paddingBottom: 42 }}>
      <View style={st.card}>
        <Text style={st.brand}>ABASE</Text>
        <Text style={st.h1}>Atualizar dados básicos</Text>
        <Text style={st.p}>Preencha seus dados pessoais, endereço, contato e bancário.</Text>

        <Text style={st.h2}>Documento</Text>
        <View style={st.row}>
          <View style={{ flex: 1.2 }}>
            <SelectField label="Tipo" value={docType} options={DOC_TYPES} onChange={v => { setDocType(v); setCpfCnpj(''); }} />
          </View>
          <View style={{ flex: 1.8 }}>
            <Text style={st.label}>{docType}</Text>
            <TextInput
              style={st.input}
              keyboardType="number-pad"
              value={maskedDoc}
              onChangeText={t => setCpfCnpj(onlyDigits(t))}
              placeholder={docType === 'CPF' ? '000.000.000-00' : '00.000.000/0000-00'}
              placeholderTextColor={PLACEHOLDER}
            />
          </View>
        </View>

        <View style={st.row}>
          <View style={st.col}>
            <Text style={st.label}>Nome completo</Text>
            <TextInput style={st.input} value={fullName} onChangeText={v => setFullName(v.toUpperCase())} autoCapitalize="characters" />
          </View>
          <View style={st.col}>
            <Text style={st.label}>Data de nascimento</Text>
            <TextInput
              style={st.input} keyboardType="number-pad"
              value={maskDateBR(birthDate)} onChangeText={setBirthDate}
              placeholder="dd/mm/aaaa" placeholderTextColor={PLACEHOLDER}
            />
          </View>
        </View>

        <View style={st.row}>
          <View style={st.col}>
            <Text style={st.label}>Profissão (opcional)</Text>
            <TextInput style={st.input} value={profession} onChangeText={setProfession} />
          </View>
          <SelectField label="Estado civil" value={marital} options={ESTADO_CIVIL} onChange={setMarital} />
        </View>

        <View style={st.row}>
          <View style={st.col}>
            <Text style={st.label}>RG (opcional)</Text>
            <TextInput style={st.input} value={rg} onChangeText={setRg} />
          </View>
          <View style={st.col}>
            <Text style={st.label}>Órgão expedidor (opcional)</Text>
            <TextInput style={st.input} value={orgaoExpedidor} onChangeText={setOrgaoExpedidor} placeholder="SSP/UF" placeholderTextColor={PLACEHOLDER} />
          </View>
        </View>

        <Text style={st.h2}>Endereço</Text>
        <View style={st.row}>
          <View style={st.col}>
            <Text style={st.label}>CEP</Text>
            <TextInput style={st.input} keyboardType="number-pad" value={maskCEP(cep)} onChangeText={setCep} placeholder="00000-000" placeholderTextColor={PLACEHOLDER} />
            {loadingCEP && <Text style={st.muted}>consultando CEP…</Text>}
          </View>
          <View style={st.col}>
            <Text style={st.label}>Logradouro</Text>
            <TextInput style={st.input} value={address} onChangeText={v => setAddress(v.toUpperCase())} />
          </View>
        </View>

        <View style={st.row}>
          <View style={[st.col, { flex: 0.8 }]}>
            <Text style={st.label}>Número (opcional)</Text>
            <TextInput style={st.input} value={addressNumber} onChangeText={setAddressNumber} placeholder="Nº" placeholderTextColor={PLACEHOLDER} />
          </View>
          <View style={st.col}>
            <Text style={st.label}>Complemento (opcional)</Text>
            <TextInput style={st.input} value={complement} onChangeText={setComplement} placeholder="APT, BLOCO..." placeholderTextColor={PLACEHOLDER} />
          </View>
        </View>

        <View style={st.row}>
          <View style={st.col}>
            <Text style={st.label}>Bairro (opcional)</Text>
            <TextInput style={st.input} value={neighborhood} onChangeText={v => setNeighborhood(v.toUpperCase())} />
          </View>
          <View style={st.col}>
            <Text style={st.label}>Cidade</Text>
            <TextInput style={st.input} value={city} onChangeText={v => setCity(v.toUpperCase())} />
          </View>
          <View style={[st.col, { flex: 0.6 }]}>
            <SelectField label="UF" value={uf} options={UF_OPTIONS} onChange={setUf} />
          </View>
        </View>

        <Text style={st.h2}>Contato & vínculo</Text>
        <View style={st.row}>
          <View style={st.col}>
            <Text style={st.label}>Celular (opcional)</Text>
            <TextInput style={st.input} keyboardType="number-pad" value={maskPhoneBR(cellphone)} onChangeText={setCellphone} placeholder="(00) 9 0000-0000" placeholderTextColor={PLACEHOLDER} />
          </View>
          <View style={st.col}>
            <Text style={st.label}>E-mail</Text>
            <TextInput style={st.input} autoCapitalize="none" keyboardType="email-address" value={email} onChangeText={setEmail} />
          </View>
        </View>

        <View style={st.row}>
          <View style={st.col}>
            <Text style={st.label}>Órgão público (opcional)</Text>
            <TextInput style={st.input} value={orgaoPublico} onChangeText={v => setOrgaoPublico(v.toUpperCase())} />
          </View>
          <SelectField label="Situação do servidor" value={situacaoServidor} options={SITUACAO_SERVIDOR} onChange={setSituacaoServidor} />
        </View>

        <Text style={st.label}>Matrícula (opcional)</Text>
        <TextInput style={st.input} value={matricula} onChangeText={setMatricula} />

        <Text style={st.h2}>Dados bancários</Text>
        <View style={st.row}>
          <View style={st.col}>
            <Text style={st.label}>Banco (opcional)</Text>
            <TextInput style={st.input} value={bankName} onChangeText={v => setBankName(v.toUpperCase())} placeholder="BANCO" placeholderTextColor={PLACEHOLDER} />
          </View>
          <View style={[st.col, { flex: 0.9 }]}>
            <Text style={st.label}>Agência</Text>
            <TextInput style={st.input} keyboardType="number-pad" value={bankAgency} onChangeText={setBankAgency} placeholder="0000" placeholderTextColor={PLACEHOLDER} />
          </View>
          <View style={st.col}>
            <Text style={st.label}>Conta</Text>
            <TextInput style={st.input} keyboardType="number-pad" value={bankAccount} onChangeText={setBankAccount} placeholder="00000-0" placeholderTextColor={PLACEHOLDER} />
          </View>
        </View>

        <View style={st.row}>
          <SelectField label="Tipo de conta" value={accountType} options={ACCOUNT_TYPES} onChange={setAccountType} />
          <View style={st.col}>
            <Text style={st.label}>Chave PIX (opcional)</Text>
            <TextInput style={st.input} value={pixKey} onChangeText={setPixKey} placeholder="CPF/E-mail/Tel" placeholderTextColor={PLACEHOLDER} />
          </View>
        </View>

        <Text style={st.h2}>Anexos essenciais</Text>
        {(Object.keys(docLabels) as DocKey[]).map(key => {
          const f = files[key] || null;
          return (
            <View key={key} style={st.attach}>
              <Text style={st.attachTitle}>{docLabels[key]}</Text>
              <Text style={st.attachHint}>Imagens (Galeria) — até 10MB.</Text>
              <View style={{ flexDirection: 'row', gap: 10, marginTop: 8 }}>
                <TouchableOpacity onPress={() => pickFromGallery(key)} style={st.ghostBtn}>
                  <Text style={st.ghostBtnText}>{f ? 'Trocar' : 'Galeria'}</Text>
                </TouchableOpacity>
                {!!f && (
                  <TouchableOpacity onPress={() => setFile(key, null)} style={[st.ghostBtn, { borderColor: '#ef4444' }]}>
                    <Text style={[st.ghostBtnText, { color: '#ef4444' }]}>Remover</Text>
                  </TouchableOpacity>
                )}
              </View>
              {f?.name ? <Text style={st.fileName}>{f.name}</Text> : null}
            </View>
          );
        })}

        <TouchableOpacity disabled={!canSubmit} onPress={submit} style={[st.btn, { opacity: canSubmit ? 1 : 0.5 }]}>
          {submitting ? <ActivityIndicator color="#012b34" /> : <Text style={st.btnText}>Salvar dados</Text>}
        </TouchableOpacity>

        <TouchableOpacity style={st.backBtn} onPress={() => router.back()}>
          <Text style={st.backBtnText}>Voltar</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const st = StyleSheet.create({
  page: { flex: 1, backgroundColor: BG },
  card: { borderRadius: 14, borderWidth: 1, borderColor: BORDER, backgroundColor: CARD, padding: 14 },
  brand: { color: BRAND, textAlign: 'center', fontSize: 28, fontWeight: '800', letterSpacing: 6, marginBottom: 6 },
  h1: { color: INK, fontSize: 18, fontWeight: '700' },
  p: { color: MUTED, marginBottom: 12 },
  h2: { color: INK, fontWeight: '700', marginTop: 10, marginBottom: 6, fontSize: 15 },
  row: { flexDirection: 'row', gap: 10 },
  col: { flex: 1 },
  label: { color: INK, marginBottom: 6, fontSize: 12, opacity: 0.9 },
  input: {
    backgroundColor: INPUT_BG, borderWidth: 1, borderColor: BORDER, borderRadius: 10,
    color: INK, paddingHorizontal: 12,
    paddingVertical: Platform.select({ ios: 12, android: 10 }) as number,
    marginBottom: 8,
  },
  muted: { color: MUTED, fontSize: 12, marginTop: 4 },
  selectBox: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: INPUT_BG, borderWidth: 1, borderColor: BORDER, borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: Platform.select({ ios: 12, android: 10 }) as number,
    marginBottom: 8,
  },
  selectValue: { color: INK, flex: 1, fontSize: 14 },
  chevron: { color: MUTED, fontSize: 12 },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'center', alignItems: 'center', padding: 24 },
  modalCard: { backgroundColor: CARD, borderRadius: 14, borderWidth: 1, borderColor: BORDER, padding: 16, width: '100%', maxHeight: '80%' },
  modalTitle: { color: INK, fontWeight: '700', fontSize: 16, marginBottom: 12 },
  optRow: { borderWidth: 1, borderColor: BORDER, borderRadius: 10, padding: 12, marginBottom: 8 },
  optText: { color: INK, fontSize: 14 },
  cancelBtn: { marginTop: 8, borderWidth: 1, borderColor: '#ef4444', borderRadius: 10, alignItems: 'center', paddingVertical: 12 },
  cancelTxt: { color: '#ef4444', fontWeight: '700' },
  attach: { marginTop: 8, padding: 12, borderRadius: 12, borderWidth: 1, borderColor: BORDER, backgroundColor: INPUT_BG },
  attachTitle: { color: INK, fontWeight: '700' },
  attachHint: { color: MUTED, fontSize: 12, marginTop: 2 },
  ghostBtn: { borderWidth: 1, borderColor: BRAND, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 8 },
  ghostBtnText: { color: BRAND, fontWeight: '700' },
  fileName: { color: MUTED, marginTop: 6, fontSize: 12 },
  btn: { marginTop: 14, height: 50, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: BRAND },
  btnText: { color: '#012b34', fontWeight: '800', fontSize: 16 },
  backBtn: { marginTop: 10, borderRadius: 12, borderWidth: 1, borderColor: BORDER, alignItems: 'center', paddingVertical: 13 },
  backBtnText: { color: MUTED, fontWeight: '700' },
});
