# Guia de Migração: App Mobile ABASE → Backend Django

**App**: `abase_mobile/Abase_mobile_legado/abasev2app`
**Backend novo**: Django DRF com JWT, rodando localmente em Docker na porta 8000
**Objetivo**: Ajustar o app legado para consumir o novo backend, mantendo toda a estrutura, telas e navegação existentes.

---

## 1. Como Abrir e Rodar o Projeto

### Pré-requisitos
- Node.js 18+
- JDK 17 (para Android)
- Android Studio + Android SDK 36 instalado
- Para iOS: macOS + Xcode 15 + CocoaPods (`brew install cocoapods`)

### Instalar dependências

```bash
cd abase_mobile/Abase_mobile_legado/abasev2app

npm install

# iOS apenas (macOS):
cd ios && bundle exec pod install && cd ..
```

### Rodar em desenvolvimento

```bash
# Emulador Android (Android Studio deve estar aberto com um AVD rodando)
npm run android

# Dispositivo físico Android (conectado via USB com USB Debugging ativo)
npm run android

# Simulador iOS (macOS apenas)
npm run ios

# Apenas o Metro bundler (sem abrir emulador)
npm start
```

### Configurar IP para dispositivo físico

No arquivo `.env` (na raiz do app), alterar a URL base para o IP da máquina de desenvolvimento:

```bash
# Para emulador Android Studio:
API_URL=http://10.0.2.2:8000/api/v1

# Para dispositivo físico na mesma rede WiFi:
API_URL=http://192.168.3.8:8000/api/v1

# Para produção (quando o backend Django estiver publicado):
API_URL=https://www.abasepiaui.com/api/v1
```

> **O IP 192.168.3.8 é o IP atual da máquina de desenvolvimento.** Se mudar de rede, rode `ipconfig` e atualize.

---

## 2. Como Gerar Builds

### Build Android — Debug (APK para testes)

```bash
cd android
./gradlew assembleDebug
```

APK gerado em: `android/app/build/outputs/apk/debug/app-debug.apk`

### Build Android — Release (APK assinado)

**Pré-requisito**: Ter o arquivo `abase-release-key.jks` (keystore) e configurar `android/gradle.properties`:

```properties
ABASE_UPLOAD_STORE_FILE=/caminho/para/abase-release-key.jks
ABASE_UPLOAD_STORE_PASSWORD=senha_do_keystore
ABASE_UPLOAD_KEY_ALIAS=abase-key-alias
ABASE_UPLOAD_KEY_PASSWORD=senha_da_chave
```

```bash
cd android
./gradlew assembleRelease
# ou AAB para Play Store:
./gradlew bundleRelease
```

APK: `android/app/build/outputs/apk/release/app-release.apk`
AAB: `android/app/build/outputs/bundle/release/app-release.aab`

### Build iOS (macOS apenas)

```bash
cd ios
xcodebuild -scheme Abase -configuration Release -destination generic/platform=iOS archive
```

Ou via Xcode: `Product → Archive`.

---

## 3. Mapeamento Completo: Endpoints Legado → Novo Backend

### 3.1 Autenticação

| Funcionalidade | Legado | Novo Backend | Mudança |
|---|---|---|---|
| **Login** | `POST /api/login` | `POST /api/v1/auth/login/` | Campo `login` → `cpf`. Resposta muda (JWT). |
| **Logout** | `POST /api/logout` | `POST /api/v1/auth/logout/` | Agora requer enviar `{refresh: token}` no body. |
| **Refresh Token** | ❌ não existia | `POST /api/v1/auth/refresh/` | Novo. JWT precisa de refresh periódico. |
| **Perfil do usuário** | `GET /api/me` | `GET /api/v1/auth/me/` | Resposta mais enxuta (sem bootstrap). |

### 3.2 Dados do Associado

| Funcionalidade | Legado | Novo Backend | Mudança |
|---|---|---|---|
| **Dashboard/Home** | `GET /api/home` | `GET /api/v1/app/me/` | Estrutura de resposta diferente. |
| **Mensalidades/Ciclos** | `GET /api/app/mensalidades/ciclo` | `GET /api/v1/app/mensalidades/` | Resposta agora retorna `{ciclos:[...]}`. |
| **Antecipação histórico** | `GET /api/app/antecipacao/historico` | `GET /api/v1/app/antecipacao/` | Retorna `{historico:[...]}`. |
| **Pendências docs** | `GET /api/associadodois/issues/my` | `GET /api/v1/app/pendencias/` | Retorna `{pendencias:[...]}`. |
| **Upload documento** | `POST /api/associadodois/reuploads` | `POST /api/v1/app/documentos/` | Mesmo multipart, estrutura diferente. |
| **Criar Associado** | `POST /api/associadodois/cadastro` | `POST /api/v1/associados/` | Role AGENTE obrigatória. |
| **Status cadastro** | `GET /api/associadodois/status` | Campo `status` em `GET /api/v1/app/me/` | Integrado no /me. |

### 3.3 Endpoints que **não existem** no novo backend

| Endpoint Legado | Situação |
|---|---|
| `POST /api/auth/register` | Associados são criados por agentes via `/api/v1/associados/`. Não há auto-cadastro. |
| `GET /api/associadodois/check-cpf` | Não implementado. Verificar via `POST /api/v1/associados/` (retorna erro 400 se CPF duplicado). |
| `PUT /api/associadodois/atualizar-basico` | Não implementado — usar `PATCH /api/v1/associados/{id}/` com role AGENTE. |
| `POST /api/forgot-password` | Não implementado — reset via painel admin web. |
| `POST /api/reset-password` | Não implementado — reset via painel admin web. |
| `GET/POST /api/associadodois/auxilio2/*` | Auxílio Emergencial fora do escopo do novo sistema. |
| `POST /api/associadodois/aceite-termos` | Não implementado. |
| `POST /api/associadodois/contato` | Não implementado. |

---

## 4. Diferenças nas Respostas das APIs

### 4.1 Login

**Legado** — enviava:
```json
{ "login": "43926363304", "password": "43926363304" }
```

**Novo** — envia:
```json
{ "cpf": "43926363304", "password": "43926363304" }
```

**Legado** — recebia:
```json
{
  "ok": true,
  "token": "abc123xyz",
  "token_type": "Bearer",
  "user": { "id": 1, "name": "João Silva", "email": "..." },
  "roles": ["ASSOCIADO"],
  "pessoa": { "nome_razao_social": "...", "documento": "...", ... },
  "contratos": [...],
  "resumo": { "prazo": 36, "parcelas_pagas": 12, ... },
  "dados_bancarios": { ... }
}
```

**Novo** — recebe (resposta minimalista):
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "uuid",
    "email": "43926363304@app.abase.local",
    "first_name": "João",
    "last_name": "Silva",
    "primary_role": "ASSOCIADO",
    "roles": ["ASSOCIADO"]
  }
}
```

> **Impacto**: Após login, o app deve fazer uma chamada extra a `GET /api/v1/app/me/` para obter os dados completos do associado (pessoa, contratos, resumo). O `AuthContext` precisa armazenar `access` + `refresh` (antes só armazenava `token`).

### 4.2 Home / Dados do Associado

**Legado** `GET /api/home` — retornava:
```json
{
  "pessoa": { "nome_razao_social": "João Silva", "documento": "43926363304", ... },
  "contratos": [{ "codigo": "C001", "status_contrato": "ATIVO", "prazo": 36, "parcela_valor": 150.00 }],
  "resumo": { "prazo": 36, "parcelas_pagas": 12, "percentual_pago": 33, "atraso": 0, "elegivel_antecipacao": false },
  "dados_bancarios": { "banco": "...", "agencia": "...", "conta": "..." },
  "vinculo_publico": { "orgao_publico": "...", "matricula": "..." }
}
```

**Novo** `GET /api/v1/app/me/` — retorna:
```json
{
  "associado": {
    "id": 1,
    "nome_completo": "João Silva",
    "cpf_cnpj": "43926363304",
    "matricula": "12345",
    "email": "joao@email.com",
    "telefone": "86999999999",
    "status": "ativo",
    "orgao_publico": "SEFAZ-PI",
    "cargo": "Auditor Fiscal"
  },
  "contratos": [
    {
      "id": 1,
      "codigo": "C001",
      "status": "ativo",
      "prazo_meses": 36,
      "valor_mensalidade": "150.00",
      "data_primeira_mensalidade": "2023-01-05"
    }
  ],
  "resumo": {
    "parcelas_pagas": 12,
    "parcelas_total": 36,
    "valor_mensalidade": "150.00",
    "proximo_vencimento": "2024-02-05",
    "em_atraso": 0
  },
  "pendencias": []
}
```

### 4.3 Mensalidades / Ciclos

**Legado** `GET /api/app/mensalidades/ciclo` — retornava:
```json
{
  "items": [
    { "valor": 150.00, "referencia": "2023-01", "previsao": "05/01/2023", "pago_em": "04/01/2023", "status": "pago" }
  ],
  "resumo": { "prazo": 36, "parcelas_pagas": 12, "percentual_pago": 33, "concluidas": 12 },
  "refinanciamento": { "exists": false },
  "proximo_ciclo": null
}
```

**Novo** `GET /api/v1/app/mensalidades/` — retorna:
```json
{
  "ciclos": [
    {
      "id": 1,
      "numero": 1,
      "data_inicio": "2023-01-01",
      "data_fim": "2023-12-31",
      "status": "ativo",
      "valor_total": "1800.00",
      "parcelas": [
        {
          "numero": 1,
          "referencia_mes": "2023-01-01",
          "valor": "150.00",
          "data_vencimento": "2023-01-05",
          "status": "DESCONTADO",
          "data_pagamento": "2023-01-04"
        }
      ]
    }
  ]
}
```

**Status de parcelas no novo backend**:
- `DESCONTADO` = parcela paga/descontada em folha
- `EM_ABERTO` = parcela em aberto (pendente)
- `CANCELADO` = parcela cancelada

### 4.4 Antecipação

**Legado** `GET /api/app/antecipacao/historico` — retornava:
```json
{
  "items": [
    { "referencia": "2023-01", "valor": 150.00, "pago_em": "04/01/2023", "status": "aprovado" }
  ]
}
```

**Novo** `GET /api/v1/app/antecipacao/` — retorna:
```json
{
  "historico": [
    {
      "referencia_mes": "2023-01-01",
      "valor": "150.00",
      "data_pagamento": "2023-01-04",
      "numero_parcela": 1,
      "ciclo_numero": 1
    }
  ]
}
```

### 4.5 Pendências

**Legado** `GET /api/associadodois/issues/my` — retornava:
```json
{
  "issues": [
    {
      "id": 1, "title": "Documento vencido", "status": "open",
      "required_docs": ["doc_front", "contracheque_atual"],
      "message": "Envie o documento atualizado"
    }
  ]
}
```

**Novo** `GET /api/v1/app/pendencias/` — retorna:
```json
{
  "pendencias": [
    {
      "id": 1,
      "tipo": "DOCUMENTO",
      "descricao": "Documento vencido",
      "status": "aberta",
      "created_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

---

## 5. Arquivos a Modificar no App

### Ordem de prioridade (do mais crítico ao menos)

#### 5.1 `.env` — Trocar URLs

**Arquivo**: `abasev2app/.env`

```bash
# NOVO BACKEND LOCAL (desenvolvimento)
API_URL=http://10.0.2.2:8000/api/v1

# Auth
LOGIN_API_URL=http://10.0.2.2:8000/api/v1/auth/login/
LOGOUT_API_URL=http://10.0.2.2:8000/api/v1/auth/logout/
HOME_API_URL=http://10.0.2.2:8000/api/v1/app/me/
ME_API_URL=http://10.0.2.2:8000/api/v1/auth/me/
REFRESH_API_URL=http://10.0.2.2:8000/api/v1/auth/refresh/

# App endpoints
APP_MENSALIDADES_URL=http://10.0.2.2:8000/api/v1/app/mensalidades/
APP_ANTECIPACAO_URL=http://10.0.2.2:8000/api/v1/app/antecipacao/
APP_PENDENCIAS_URL=http://10.0.2.2:8000/api/v1/app/pendencias/
APP_DOCUMENTOS_URL=http://10.0.2.2:8000/api/v1/app/documentos/
ASSOCIADOS_URL=http://10.0.2.2:8000/api/v1/associados/

# Remover/desativar:
# REGISTER_API_URL (não existe mais)
# ASSOCIADODOIS_CADASTRO_URL (usar ASSOCIADOS_URL)
# ASSOCIADODOIS_STATUS_URL (usar HOME_API_URL)
# ASSOCIADODOIS_ISSUES_MY_URL (usar APP_PENDENCIAS_URL)
# ASSOCIADODOIS_REUPLOADS_URL (usar APP_DOCUMENTOS_URL)
# ATUALIZAR_BASICO_URL (não implementado)
# AUXILIO2_* (fora do escopo)
```

#### 5.2 `services/api/http.ts` — Suporte a JWT

O client HTTP precisa saber que os tokens agora são JWT com `access` + `refresh`.
A diferença principal: o token agora tem expiração curta (~5 min por padrão no simplejwt). Quando expirar, retorna 401 e precisa fazer refresh automático.

**Estratégia de refresh automático** (adicionar no http.ts ou AuthContext):
```typescript
// Se receber 401, tentar POST /api/v1/auth/refresh/ com o refreshToken
// Se refresh OK → repetir a requisição original com novo access token
// Se refresh falhar → logout()
```

#### 5.3 `context/AuthContext.tsx` — Armazenar access + refresh

**Estado atual**: Armazena `{ user, token, roles, bootstrap }`
**Estado novo**: Armazenar `{ user, accessToken, refreshToken, roles, bootstrap }`

```typescript
// AsyncStorage key: @Abase:authState
// Formato novo:
{
  user: { id, email, first_name, last_name, primary_role, roles },
  accessToken: "eyJ...",
  refreshToken: "eyJ...",
  bootstrap: null  // carregar separado via /app/me/
}
```

**Fluxo de login novo**:
1. `POST /api/v1/auth/login/` com `{cpf, password}`
2. Salvar `access` e `refresh` no AsyncStorage
3. Chamar `GET /api/v1/app/me/` para obter `bootstrap` (pessoa, contratos, resumo)
4. Navegar para Home

#### 5.4 `services/api/authService.ts` — Adaptar login

**Campo `login` → `cpf`**:
```typescript
// Antes:
export async function loginApi(login: string, password: string) {
  return http(LOGIN_API_URL, { method: 'POST', body: JSON.stringify({ login, password }) });
}

// Depois (simplificado — app só usa CPF):
export async function loginApi(cpf: string, password: string) {
  return http(LOGIN_API_URL, { method: 'POST', body: JSON.stringify({ cpf, password }) });
}
```

**Resposta do login muda**:
- Antes: `{ ok, token, user, roles, pessoa, contratos, resumo, ... }`
- Depois: `{ access, refresh, user: { id, email, first_name, last_name, primary_role, roles } }`

**Após login**, chamar `GET /api/v1/app/me/` para obter bootstrap completo:
- `associado` → equivale ao antigo `pessoa`
- `contratos` → lista de contratos
- `resumo` → resumo financeiro
- `pendencias` → pendências da esteira

#### 5.5 `services/api/homeService.ts` — Adaptar para /app/me/

```typescript
// Antes: GET /api/home → HomeData{pessoa, contratos, resumo, ...}
// Depois: GET /api/v1/app/me/ → {associado, contratos, resumo, pendencias}
```

**Mapeamento de campos** para manter as telas funcionando:

| Legado | Novo | Observação |
|---|---|---|
| `pessoa.nome_razao_social` | `associado.nome_completo` | |
| `pessoa.documento` | `associado.cpf_cnpj` | |
| `pessoa.celular` | `associado.telefone` | |
| `pessoa.orgao_publico` | `associado.orgao_publico` | |
| `contratos[0].status_contrato` | `contratos[0].status` | |
| `contratos[0].parcela_valor` | `contratos[0].valor_mensalidade` | |
| `contratos[0].prazo` | `contratos[0].prazo_meses` | |
| `resumo.parcelas_pagas` | `resumo.parcelas_pagas` | ✅ igual |
| `resumo.atraso` | `resumo.em_atraso` | |
| `resumo.percentual_pago` | Calcular: `(pagas/total)*100` | |
| `resumo.elegivel_antecipacao` | Não existe mais | Remover ou calcular |
| `dados_bancarios.*` | Não retornado no /me | Remover da tela se exibir |
| `vinculo_publico.*` | `associado.orgao_publico`, `associado.cargo` | |

#### 5.6 `services/api/mensalidadesService.ts` — Adaptar ciclos

```typescript
// Antes: GET /api/app/mensalidades/ciclo?cpf=xxx&...
// Depois: GET /api/v1/app/mensalidades/  (sem parâmetros, baseado no usuário logado)
```

**Mapeamento de campos** para `MensalidadesScreen`:

| Legado | Novo | Observação |
|---|---|---|
| `items[].referencia` `"YYYY-MM"` | `ciclos[].parcelas[].referencia_mes` `"YYYY-MM-DD"` | Pegar primeiros 7 chars |
| `items[].previsao` `"DD/MM/YYYY"` | `ciclos[].parcelas[].data_vencimento` `"YYYY-MM-DD"` | Reformatar |
| `items[].pago_em` `"DD/MM/YYYY"` | `ciclos[].parcelas[].data_pagamento` `"YYYY-MM-DD"` | Reformatar |
| `items[].status` `"pago"` | `ciclos[].parcelas[].status` `"DESCONTADO"` | Mapear: DESCONTADO→pago, EM_ABERTO→pendente |
| `items[].valor` | `ciclos[].parcelas[].valor` | |
| `resumo.total_ciclo` | `ciclos[].parcelas.length` | |
| `resumo.concluidas` | Contar parcelas com status DESCONTADO | |

#### 5.7 `services/api/antecipacaoService.ts` — Adaptar histórico

```typescript
// Antes: GET /api/app/antecipacao/historico?cpf=xxx
// Depois: GET /api/v1/app/antecipacao/
```

**Mapeamento**:

| Legado `items[]` | Novo `historico[]` |
|---|---|
| `referencia` `"YYYY-MM"` | `referencia_mes` `"YYYY-MM-DD"` |
| `valor` | `valor` |
| `pago_em` `"DD/MM/YYYY"` | `data_pagamento` `"YYYY-MM-DD"` |
| `status` `"aprovado"` | Sempre pago (só retorna DESCONTADO) |

#### 5.8 `services/api/pendenciasService.ts` — Adaptar pendências

```typescript
// Antes: GET /api/associadodois/issues/my → {issues:[{id, title, status, required_docs, message}]}
// Depois: GET /api/v1/app/pendencias/ → {pendencias:[{id, tipo, descricao, status, created_at}]}
```

**Mapeamento**:

| Legado `issues[]` | Novo `pendencias[]` |
|---|---|
| `id` | `id` |
| `title` | `descricao` |
| `status` `"open"` | `status` `"aberta"` |
| `required_docs[]` | Não existe no novo — remover lista de docs |
| `message` | `tipo` |

#### 5.9 `screens/LoginScreen.tsx` — Mudança mínima

O `LoginScreen` atual já envia CPF como dígitos para o backend (via `cleanCpf()`).
**Única mudança**: o campo no JSON deve ser `cpf` em vez de `login`.

```typescript
// Antes (authService.ts):
body: JSON.stringify({ login: cpfOrEmail, password })

// Depois:
body: JSON.stringify({ cpf: cpfDigits, password })
```

> **Nota**: O app legado suportava login por email também. No novo sistema, apenas CPF funciona para associados. A tela pode ser simplificada para aceitar apenas CPF.

#### 5.10 `screens/MensalidadesScreen.tsx` — Adaptar exibição de ciclos

A tela exibe uma lista plana de parcelas. Com o novo backend, os dados chegam agrupados por ciclo.
O adaptador de dados deve **aplainar** os ciclos em itens individuais:

```typescript
// Converter resposta nova em formato antigo para reusar componentes:
function adaptCiclosToItems(ciclos) {
  return ciclos.flatMap(ciclo =>
    ciclo.parcelas.map(parcela => ({
      valor: parseFloat(parcela.valor),
      referencia: parcela.referencia_mes.substring(0, 7), // "YYYY-MM"
      previsao: formatDateBR(parcela.data_vencimento),    // "DD/MM/YYYY"
      pago_em: parcela.data_pagamento ? formatDateBR(parcela.data_pagamento) : null,
      status: parcela.status === 'DESCONTADO' ? 'pago' : 'pendente',
      ciclo_numero: ciclo.numero,
    }))
  );
}
```

---

## 6. Telas a Desativar ou Adaptar

| Tela | Ação | Motivo |
|---|---|---|
| **RegisterScreen** | Remover ou desativar link | Não há auto-cadastro; agentes criam via web |
| **ForgotPasswordScreen** | Remover ou substituir | Não implementado no novo backend |
| **ResetPasswordScreen** | Remover ou substituir | Não implementado no novo backend |
| **AuxilioEmergencialDois** | Remover do menu | Fora do escopo do novo sistema |
| **EsperaScreen** | Adaptar | Usar campo `status` de `/app/me/` |
| **AtualizarCadastroScreen** | Desativar por ora | Endpoint não implementado |
| **CadastroAssociadoScreen** | Manter para agentes | Usar `POST /api/v1/associados/` |

---

## 7. Fluxo JWT — Como Implementar Refresh Automático

O sistema legado usava tokens sem expiração. O novo usa JWT com expiração curta.
É necessário implementar um mecanismo de refresh automático no `http.ts` ou `AuthContext`.

### Estratégia recomendada

```typescript
// Em http.ts — adicionar lógica de refresh:
async function http<T>(url: string, opts = {}): Promise<T> {
  const { accessToken, refreshToken } = await getStoredTokens();

  // Primeira tentativa
  try {
    return await _rawRequest<T>(url, opts, accessToken);
  } catch (err) {
    // Se 401 e temos refresh token:
    if (err.status === 401 && refreshToken) {
      const newTokens = await refreshAccessToken(refreshToken);
      if (newTokens) {
        await saveTokens(newTokens);
        // Repetir requisição com novo token
        return await _rawRequest<T>(url, opts, newTokens.access);
      }
      // Refresh falhou → logout
      await logout();
      throw err;
    }
    throw err;
  }
}

// Refresh token:
async function refreshAccessToken(refresh: string) {
  const res = await fetch(REFRESH_API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  });
  if (!res.ok) return null;
  const data = await res.json();
  return { access: data.access, refresh: data.refresh || refresh };
}
```

### AsyncStorage — novo formato

```typescript
// @Abase:authState agora armazena:
{
  user: { id, email, first_name, last_name, primary_role, roles },
  accessToken: "eyJhbGci...",
  refreshToken: "eyJhbGci...",
  bootstrap: {
    associado: { id, nome_completo, cpf_cnpj, ... },
    contratos: [...],
    resumo: { parcelas_pagas, parcelas_total, valor_mensalidade, proximo_vencimento, em_atraso },
    pendencias: [...]
  }
}
```

---

## 8. Cadastro de Novo Associado (Fluxo do Agente)

**Tela**: `CadastroAssociadoScreen.tsx`
**Antes**: `POST /api/associadodois/cadastro` com FormData
**Depois**: `POST /api/v1/associados/` com JSON + arquivos via PATCH/PUT ou endpoints separados

### Endpoint novo

```
POST /api/v1/associados/
Authorization: Bearer {access_token}  ← token de um usuário com role AGENTE
```

**Payload mínimo aceito**:
```json
{
  "nome_completo": "João Silva",
  "cpf_cnpj": "43926363304",
  "tipo_documento": "CPF",
  "email": "joao@email.com",
  "telefone": "86999999999",
  "data_nascimento": "1985-03-15",
  "orgao_publico": "SEFAZ-PI",
  "cep": "64000000",
  "logradouro": "Rua Principal",
  "numero": "100",
  "bairro": "Centro",
  "cidade": "Teresina",
  "uf": "PI"
}
```

**Resposta**: dados completos do associado criado com `id`.

> **Importante**: O agente precisa estar logado com role AGENTE para criar associados. O associado recém-criado pode logar com CPF + senha padrão (CPF digits) após ser criado via `create_associado_users` ou após vinculação manual.

---

## 9. Checklist de Implementação

### Fase 1 — Crítico (para login funcionar)
- [ ] Atualizar `.env` com URLs novas
- [ ] Adaptar `authService.ts`: campo `login` → `cpf`, tratar resposta JWT
- [ ] Adaptar `AuthContext.tsx`: armazenar `accessToken` + `refreshToken`
- [ ] Implementar refresh automático no `http.ts`
- [ ] Após login, chamar `/app/me/` para bootstrap

### Fase 2 — Telas principais
- [ ] Adaptar `homeService.ts` para nova estrutura `/app/me/`
- [ ] Adaptar `HomeScreen.tsx` para novos nomes de campos
- [ ] Adaptar `mensalidadesService.ts` para `/app/mensalidades/`
- [ ] Adaptar `MensalidadesScreen.tsx` para nova estrutura de ciclos
- [ ] Adaptar `antecipacaoService.ts` para `/app/antecipacao/`
- [ ] Adaptar `pendenciasService.ts` para `/app/pendencias/`

### Fase 3 — Funcionalidades secundárias
- [ ] Adaptar `CadastroAssociadoScreen.tsx` para `POST /api/v1/associados/`
- [ ] Remover telas sem equivalente no novo backend (Register, ForgotPassword, Auxílio2)
- [ ] Adaptar `PerfilScreen.tsx` para novos campos do `/app/me/`

### Fase 4 — Testes
- [ ] Testar login com CPF `43926363304` senha `43926363304` (usuário AGNALDO)
- [ ] Verificar ciclos e parcelas carregam corretamente
- [ ] Verificar logout e re-login funcionam
- [ ] Testar refresh token automático (simular expiração)
- [ ] Testar no emulador Android
- [ ] Testar no dispositivo físico (ajustar IP no `.env`)

---

## 10. Senhas dos Associados

No novo backend, todos os associados têm senha padrão = **CPF sem pontuação**.

| CPF digitado | Senha para login |
|---|---|
| `439.263.633-04` | `43926363304` |
| `496.846.393-68` | `49684639368` |

Para resetar a senha de um associado específico via Django admin:
```bash
docker exec abase-v2-backend-1 python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
u = User.objects.get(email='43926363304@app.abase.local')
u.set_password('nova_senha')
u.save()
print('Senha alterada')
"
```

---

## 11. Estrutura do Projeto (Referência)

```
abase_mobile/Abase_mobile_legado/abasev2app/
├── .env                          ← ⚠️ ALTERAR TODAS AS URLs
├── screens/
│   ├── LoginScreen.tsx           ← ⚠️ Mudar campo login→cpf
│   ├── HomeScreen.tsx            ← ⚠️ Adaptar campos da resposta
│   ├── MensalidadesScreen.tsx    ← ⚠️ Adaptar estrutura de ciclos
│   ├── AntecipacaoScreen.tsx     ← ⚠️ Adaptar campos
│   ├── PendenciasDocumentosScreen.tsx  ← ⚠️ Adaptar campos
│   ├── CadastroAssociadoScreen.tsx     ← ⚠️ Novo endpoint
│   ├── RegisterScreen.tsx        ← ❌ Desativar
│   ├── ForgotPasswordScreen.tsx  ← ❌ Desativar
│   ├── AuxilioEmergencialDois.tsx ← ❌ Remover do menu
│   └── PerfilScreen.tsx          ← ⚠️ Adaptar campos
├── services/api/
│   ├── http.ts                   ← ⚠️ Adicionar refresh JWT automático
│   ├── authService.ts            ← ⚠️ Reescrever para JWT
│   ├── homeService.ts            ← ⚠️ Apontar para /app/me/
│   ├── mensalidadesService.ts    ← ⚠️ Apontar para /app/mensalidades/
│   ├── antecipacaoService.ts     ← ⚠️ Apontar para /app/antecipacao/
│   ├── pendenciasService.ts      ← ⚠️ Apontar para /app/pendencias/
│   └── cadastroService.ts        ← ⚠️ Apontar para /associados/
└── context/AuthContext/
    └── AuthContext.tsx            ← ⚠️ Armazenar access+refresh tokens
```

---

## 12. Configurações de Build Android (Referência)

**Arquivo**: `android/app/build.gradle`

```groovy
android {
    compileSdk = 36
    defaultConfig {
        applicationId "com.abase.abasepi"
        minSdk = 24
        targetSdk = 36
        versionCode 8         // Incrementar a cada release
        versionName "1.0.7"   // Versão exibida na Play Store
    }
}
```

**Para gerar keystore nova** (se não existir):
```bash
keytool -genkeypair -v -storetype PKCS12 \
  -keystore abase-release-key.jks \
  -alias abase-key-alias \
  -keyalg RSA -keysize 2048 \
  -validity 10000
```

---

*Documento gerado em 2026-03-15 com base na análise completa do app legado e novo backend Django.*
