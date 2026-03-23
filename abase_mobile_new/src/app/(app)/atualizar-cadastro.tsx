import React, { useEffect, useRef, useState } from 'react';
import {
  Alert, FlatList, Keyboard, KeyboardAvoidingView, Modal,
  Platform, Pressable, ScrollView, StyleSheet, Text,
  TextInput, TouchableOpacity, View,
} from 'react-native';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { useAuth } from '@/context/AuthContext';
import { checkCpfDuplicadoBasico, type MaritalStatus } from '@/services/api/cadastroService';
import { submitAtualizarBasico } from '@/services/api/atualizarService';
import type { CadastroAssociadoPayload } from '@/services/api/cadastroService';
import type { LocalFile } from '@/types';

const COLORS = {
  BG: '#0b0f14',
  PANEL: '#111827',
  INPUT_BG: '#0f172a',
  INPUT_TEXT: '#e5e7eb',
  PLACEHOLDER: '#9aa3af',
  LABEL: '#e5e7eb',
  BORDER_PANEL: 'rgba(148,163,184,0.35)',
  BORDER_FIELD: 'rgba(148,163,184,0.55)',
  BRAND: '#22d3ee',
  BTN_BG: '#22d3ee',
  BTN_TEXT: '#06121f',
};
const { BG, PANEL, INPUT_BG, INPUT_TEXT, PLACEHOLDER, LABEL, BORDER_PANEL, BORDER_FIELD, BRAND, BTN_BG, BTN_TEXT } = COLORS;

const MAX_FILE_BYTES = 10 * 1024 * 1024;

const MSG_VERIFICACAO_GENERICA =
  'Não foi possível concluir a verificação com os dados informados. ' +
  'Se você já possui cadastro, acesse com seu CPF e matrícula. ' +
  'Se precisar, entre em contato com o suporte.';

const onlyDigits = (s: string) => (s || '').replace(/\D+/g, '');

const maskCPF = (v: string) => {
  const d = onlyDigits(v).slice(0, 11);
  return d
    .replace(/^(\d{3})(\d)/, '$1.$2')
    .replace(/^(\d{3})\.(\d{3})(\d)/, '$1.$2.$3')
    .replace(/\.(\d{3})(\d)/, '.$1-$2');
};

const maskCNPJ = (v: string) => {
  const d = onlyDigits(v).slice(0, 14);
  return d
    .replace(/^(\d{2})(\d)/, '$1.$2')
    .replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3')
    .replace(/\.(\d{3})(\d)/, '.$1/$2')
    .replace(/(\d{4})(\d)/, '$1-$2');
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
  if (d.length === 0) return '';
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
  label,
  value,
  placeholder = 'Selecione',
  options,
  onChange,
}: {
  label: string;
  value: T | '';
  placeholder?: string;
  options: SelectOption<T>[];
  onChange: (v: T) => void;
}) {
  const [open, setOpen] = useState(false);
  const selected = options.find(o => o.value === value);
  return (
    <View style={{ flex: 1 }}>
      <Text style={s.label}>{label}</Text>
      <Pressable style={s.selectWrap} onPress={() => setOpen(true)}>
        <Text style={[s.selectValue, !selected && { color: PLACEHOLDER }]}>
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
              keyExtractor={(item) => String(item.value)}
              renderItem={({ item }) => (
                <Pressable
                  style={[s.optionRow, item.value === value && { borderColor: BTN_BG }]}
                  onPress={() => { onChange(item.value as T); setOpen(false); }}
                >
                  <Text style={s.optionText}>{item.label}</Text>
                </Pressable>
              )}
            />
            <TouchableOpacity style={s.cancelBtn} onPress={() => setOpen(false)} activeOpacity={0.85}>
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
].map(a => ({ label: a, value: a as UF }));

const DOC_TYPE_OPTIONS: SelectOption<'CPF' | 'CNPJ'>[] = [
  { label: 'CPF', value: 'CPF' },
  { label: 'CNPJ', value: 'CNPJ' },
];

export default function AtualizarCadastroScreen() {
  const router = useRouter();
  const { user } = useAuth();

  const [docType, setDocType] = useState<'CPF' | 'CNPJ'>('CPF');
  const [cpfCnpj, setCpfCnpj] = useState('');
  const [docStatus, setDocStatus] = useState<'idle' | 'invalid' | 'checking' | 'ok' | 'blocked'>('idle');
  const [docHint, setDocHint] = useState<string>('');
  const docTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => { if (docTimer.current) clearTimeout(docTimer.current); }, []);

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

  const isSaveBlocked = busy || docStatus === 'checking' || docStatus === 'blocked';

  async function tryFillFromCep(raw: string) {
    const digits = onlyDigits(raw);
    if (digits.length !== 8) return;
    try {
      const r = await fetch(`https://viacep.com.br/ws/${digits}/json/`);
      const j = await r.json();
      if (!j || j.erro) return;
      setAddress((j.logradouro || '').toUpperCase());
      setNeighborhood((j.bairro || '').toUpperCase());
      setCity((j.localidade || '').toUpperCase());
      setUf((j.uf || '') as UF);
    } catch { /* noop */ }
  }

  function onChangeDocType(v: 'CPF' | 'CNPJ') {
    setDocType(v);
    setCpfCnpj('');
    setDocStatus('idle');
    setDocHint('');
    if (docTimer.current) clearTimeout(docTimer.current);
  }

  function onChangeCpfCnpj(t: string) {
    setCpfCnpj(t);
    setDocHint('');
    const digits = onlyDigits(t);
    const expected = docType === 'CPF' ? 11 : 14;
    if (!digits) { setDocStatus('idle'); return; }
    if (digits.length !== expected) { setDocStatus('invalid'); return; }
    if (docTimer.current) clearTimeout(docTimer.current);
    docTimer.current = setTimeout(async () => {
      try {
        setDocStatus('checking');
        setDocHint('Verificando documento...');
        const res = await checkCpfDuplicadoBasico(digits);
        if (res?.exists) {
          setDocStatus('blocked');
          setDocHint(MSG_VERIFICACAO_GENERICA);
        } else {
          setDocStatus('ok');
          setDocHint('');
        }
      } catch {
        setDocStatus('idle');
        setDocHint('');
      }
    }, 450);
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
        Alert.alert('Permissão negada', 'Acesso à galeria é necessário para enviar documentos.');
        return;
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
    if (docStatus === 'checking') { Alert.alert('Atenção', 'Aguarde a verificação do documento.'); return; }
    if (docStatus === 'blocked') { Alert.alert('Atenção', docHint || MSG_VERIFICACAO_GENERICA); return; }
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
      files: {
        cpf_frente: docs.cpf_frente ?? null,
        cpf_verso: docs.cpf_verso ?? null,
        comp_endereco: docs.comp_endereco ?? null,
        contracheque_atual: docs.contracheque_atual ?? null,
      },
    };

    try {
      setBusy(true);
      const out = await submitAtualizarBasico(payload);
      Alert.alert('Pronto!', out?.message || 'Dados atualizados com sucesso.', [
        { text: 'OK', onPress: () => router.back() },
      ]);
    } catch (e: any) {
      Alert.alert('Erro', e?.message || 'Não foi possível atualizar seus dados.');
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
          <View style={s.panel}>
            <Text style={s.brand}>ABASE</Text>
            <Text style={s.h1}>Atualizar Cadastro</Text>
            <Text style={s.p}>Preencha ou atualize seus dados pessoais, endereço e informações bancárias.</Text>

            {/* Documento */}
            <Text style={s.h2}>Documento</Text>
            <View style={s.row}>
              <SelectField
                label="Tipo"
                value={docType}
                options={DOC_TYPE_OPTIONS}
                onChange={onChangeDocType}
              />
              <View style={{ flex: 2 }}>
                <Text style={s.label}>{docType}</Text>
                <TextInput
                  style={[s.input, docStatus === 'blocked' && { borderColor: '#ef4444' }]}
                  keyboardType="number-pad"
                  value={maskedDoc}
                  onChangeText={onChangeCpfCnpj}
                  placeholder={docType === 'CPF' ? '000.000.000-00' : '00.000.000/0000-00'}
                  placeholderTextColor={PLACEHOLDER}
                />
                {!!docHint && (
                  <Text style={[s.hint, docStatus === 'blocked' && { color: '#ef4444' }]}>{docHint}</Text>
                )}
              </View>
            </View>

            <Text style={s.label}>Nome completo</Text>
            <TextInput style={s.input} value={fullName} onChangeText={v => setFullName(v.toUpperCase())} autoCapitalize="characters" />

            <View style={s.row}>
              <View style={{ flex: 1 }}>
                <Text style={s.label}>Data de nascimento</Text>
                <TextInput
                  style={s.input}
                  keyboardType="number-pad"
                  value={maskDateBR(birthDate)}
                  onChangeText={setBirthDate}
                  placeholder="dd/mm/aaaa"
                  placeholderTextColor={PLACEHOLDER}
                />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={s.label}>Profissão (opcional)</Text>
                <TextInput style={s.input} value={profession} onChangeText={setProfession} />
              </View>
            </View>

            <View style={s.row}>
              <SelectField
                label="Estado civil"
                value={maritalStatus}
                options={ESTADOS_CIVIS}
                onChange={v => setMaritalStatus(v as MaritalStatus)}
              />
              <View style={{ flex: 1 }}>
                <Text style={s.label}>RG (opcional)</Text>
                <TextInput style={s.input} value={rg} onChangeText={setRg} />
              </View>
            </View>

            <Text style={s.label}>Órgão expedidor (opcional)</Text>
            <TextInput style={s.input} value={orgaoExpedidor} onChangeText={setOrgaoExpedidor} placeholder="SSP/UF" placeholderTextColor={PLACEHOLDER} />

            {/* Endereço */}
            <Text style={s.h2}>Endereço</Text>
            <View style={s.row}>
              <View style={{ flex: 1 }}>
                <Text style={s.label}>CEP</Text>
                <TextInput
                  style={s.input}
                  keyboardType="number-pad"
                  value={maskCEP(cep)}
                  onChangeText={v => { setCep(v); tryFillFromCep(v); }}
                  placeholder="00000-000"
                  placeholderTextColor={PLACEHOLDER}
                />
              </View>
              <View style={{ flex: 2 }}>
                <Text style={s.label}>Logradouro</Text>
                <TextInput style={s.input} value={address} onChangeText={v => setAddress(v.toUpperCase())} />
              </View>
            </View>

            <View style={s.row}>
              <View style={{ flex: 0.8 }}>
                <Text style={s.label}>Número</Text>
                <TextInput style={s.input} value={addressNumber} onChangeText={setAddressNumber} placeholder="Nº" placeholderTextColor={PLACEHOLDER} />
              </View>
              <View style={{ flex: 1.2 }}>
                <Text style={s.label}>Complemento (opcional)</Text>
                <TextInput style={s.input} value={complement} onChangeText={v => setComplement(v.toUpperCase())} placeholder="APT, BLOCO..." placeholderTextColor={PLACEHOLDER} />
              </View>
            </View>

            <View style={s.row}>
              <View style={{ flex: 1 }}>
                <Text style={s.label}>Bairro (opcional)</Text>
                <TextInput style={s.input} value={neighborhood} onChangeText={v => setNeighborhood(v.toUpperCase())} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={s.label}>Cidade</Text>
                <TextInput style={s.input} value={city} onChangeText={v => setCity(v.toUpperCase())} />
              </View>
            </View>

            <SelectField label="UF" value={uf} options={UF_OPTIONS} onChange={v => setUf(v)} />

            {/* Contato & vínculo */}
            <Text style={s.h2}>Contato & vínculo</Text>
            <View style={s.row}>
              <View style={{ flex: 1 }}>
                <Text style={s.label}>Celular (opcional)</Text>
                <TextInput
                  style={s.input}
                  keyboardType="number-pad"
                  value={maskPhoneBR(cellphone)}
                  onChangeText={setCellphone}
                  placeholder="(00) 9 0000-0000"
                  placeholderTextColor={PLACEHOLDER}
                />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={s.label}>E-mail</Text>
                <TextInput style={s.input} autoCapitalize="none" keyboardType="email-address" value={email} onChangeText={setEmail} />
              </View>
            </View>

            <Text style={s.label}>Órgão público (opcional)</Text>
            <TextInput style={s.input} value={orgaoPublico} onChangeText={v => setOrgaoPublico(v.toUpperCase())} />

            <View style={s.row}>
              <SelectField
                label="Situação do servidor"
                value={situacaoServidor}
                options={SITUACOES_SERVIDOR.map(o => ({ ...o }))}
                onChange={setSituacaoServidor}
              />
              <View style={{ flex: 1 }}>
                <Text style={s.label}>Matrícula (opcional)</Text>
                <TextInput style={s.input} value={matriculaServidorPublico} onChangeText={v => setMatriculaServidorPublico(v.toUpperCase())} />
              </View>
            </View>

            {/* Dados bancários */}
            <Text style={s.h2}>Dados bancários</Text>
            <View style={s.row}>
              <View style={{ flex: 1.5 }}>
                <Text style={s.label}>Banco (opcional)</Text>
                <TextInput style={s.input} value={bankName} onChangeText={v => setBankName(v.toUpperCase())} placeholder="BANCO" placeholderTextColor={PLACEHOLDER} />
              </View>
              <View style={{ flex: 0.8 }}>
                <Text style={s.label}>Agência</Text>
                <TextInput style={s.input} keyboardType="number-pad" value={bankAgency} onChangeText={setBankAgency} placeholder="0000" placeholderTextColor={PLACEHOLDER} />
              </View>
            </View>

            <View style={s.row}>
              <View style={{ flex: 1 }}>
                <Text style={s.label}>Conta</Text>
                <TextInput style={s.input} keyboardType="number-pad" value={bankAccount} onChangeText={setBankAccount} placeholder="00000-0" placeholderTextColor={PLACEHOLDER} />
              </View>
              <SelectField
                label="Tipo de conta"
                value={accountType}
                options={[
                  { label: 'Corrente', value: 'corrente' },
                  { label: 'Poupança', value: 'poupanca' },
                ]}
                onChange={v => setAccountType(v as any)}
              />
            </View>

            <Text style={s.label}>Chave PIX (opcional)</Text>
            <TextInput style={s.input} value={pixKey} onChangeText={setPixKey} placeholder="CPF / E-mail / Telefone" placeholderTextColor={PLACEHOLDER} />

            {/* Anexos */}
            <Text style={s.h2}>Anexos (opcional)</Text>
            {(Object.keys(docLabels) as BasicDocKey[]).map(slot => {
              const f = docs[slot] || null;
              return (
                <View key={slot} style={s.docCard}>
                  <Text style={s.docTitle}>{docLabels[slot]}</Text>
                  <Text style={s.docHint}>Imagens (Galeria) — até 10MB.</Text>
                  {f ? (
                    <View style={{ gap: 8, marginTop: 8 }}>
                      <Text style={s.docFileName} numberOfLines={1}>{f.name}</Text>
                      <View style={s.row}>
                        <TouchableOpacity style={s.smallBtn} onPress={() => pickFromGallery(slot)} activeOpacity={0.85}>
                          <Text style={s.smallBtnTxt}>Trocar</Text>
                        </TouchableOpacity>
                        <TouchableOpacity style={s.smallBtnSolid} onPress={() => setDoc(slot, null)} activeOpacity={0.85}>
                          <Text style={s.smallBtnSolidTxt}>Remover</Text>
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

            <TouchableOpacity
              style={[s.btn, isSaveBlocked && { opacity: 0.5 }]}
              onPress={handleSubmit}
              disabled={isSaveBlocked}
              activeOpacity={0.85}
            >
              <Text style={s.btnTxt}>{busy ? 'Salvando…' : 'Salvar alterações'}</Text>
            </TouchableOpacity>

            <TouchableOpacity style={s.ghostBtn} onPress={() => router.back()} activeOpacity={0.85}>
              <Text style={s.ghostBtnTxt}>Voltar</Text>
            </TouchableOpacity>
          </View>
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: BG },
  panel: { borderRadius: 14, borderWidth: 1, borderColor: BORDER_PANEL, backgroundColor: PANEL, padding: 14 },
  brand: { color: BRAND, textAlign: 'center', fontSize: 28, fontWeight: '800', letterSpacing: 6, marginBottom: 6 },
  h1: { color: INPUT_TEXT, fontSize: 18, fontWeight: '700', marginBottom: 4 },
  p: { color: '#9aa3af', marginBottom: 12 },
  h2: { color: INPUT_TEXT, fontWeight: '700', marginTop: 14, marginBottom: 8, fontSize: 15 },
  row: { flexDirection: 'row', gap: 10, marginBottom: 10 },
  label: { color: LABEL, marginBottom: 6, fontSize: 12, opacity: 0.9 },
  input: {
    backgroundColor: INPUT_BG, borderWidth: 1, borderColor: BORDER_FIELD, borderRadius: 10,
    color: INPUT_TEXT, paddingHorizontal: 12,
    paddingVertical: Platform.select({ ios: 12, android: 10 }) as number,
    marginBottom: 10,
  },
  hint: { color: '#9aa3af', fontSize: 11, marginTop: -6, marginBottom: 8 },
  selectWrap: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: INPUT_BG, borderWidth: 1, borderColor: BORDER_FIELD, borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: Platform.select({ ios: 12, android: 10 }) as number,
    marginBottom: 10,
  },
  selectValue: { color: INPUT_TEXT, flex: 1, fontSize: 14 },
  chevron: { color: '#9aa3af', fontSize: 12, marginLeft: 6 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'center', alignItems: 'center', padding: 24 },
  modalCard: { backgroundColor: PANEL, borderRadius: 14, borderWidth: 1, borderColor: BORDER_PANEL, padding: 16, width: '100%', maxHeight: '80%' },
  modalTitle: { color: INPUT_TEXT, fontWeight: '700', fontSize: 16, marginBottom: 12 },
  optionRow: { borderWidth: 1, borderColor: BORDER_FIELD, borderRadius: 10, padding: 12, marginBottom: 8 },
  optionText: { color: INPUT_TEXT, fontSize: 14 },
  cancelBtn: { marginTop: 8, borderWidth: 1, borderColor: '#ef4444', borderRadius: 10, alignItems: 'center', paddingVertical: 12 },
  cancelTxt: { color: '#ef4444', fontWeight: '700' },
  docCard: { marginTop: 8, padding: 12, borderRadius: 12, borderWidth: 1, borderColor: BORDER_FIELD, backgroundColor: INPUT_BG },
  docTitle: { color: INPUT_TEXT, fontWeight: '700' },
  docHint: { color: '#9aa3af', fontSize: 12, marginTop: 2 },
  docFileName: { color: '#9aa3af', fontSize: 12 },
  smallBtn: { borderWidth: 1, borderColor: BRAND, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 8 },
  smallBtnTxt: { color: BRAND, fontWeight: '700', fontSize: 13 },
  smallBtnSolid: { borderWidth: 1, borderColor: '#ef4444', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 8 },
  smallBtnSolidTxt: { color: '#ef4444', fontWeight: '700', fontSize: 13 },
  btn: { marginTop: 18, height: 50, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: BTN_BG },
  btnTxt: { color: BTN_TEXT, fontWeight: '800', fontSize: 16 },
  ghostBtn: { marginTop: 10, borderRadius: 12, borderWidth: 1, borderColor: BORDER_FIELD, alignItems: 'center', paddingVertical: 13 },
  ghostBtnTxt: { color: '#cbd5e1', fontWeight: '700' },
});
