# ABASE Mobile — Documentação da Migração

## Visão Geral

Reescrita completa do app mobile legado (`abase_mobile/Abase_mobile_legado/abasev2app`) para Expo Managed Workflow **SDK 54**, com Expo Router (file-based routing) e integração com o novo backend Django 6.0 + DRF.

| Item | Legado | Novo |
|---|---|---|
| Framework | React Native 0.82.1 (bare workflow) | Expo SDK 54 (managed workflow) |
| Navegação | React Navigation (stack manual) | Expo Router 6 (file-based) |
| Token storage | AsyncStorage | expo-secure-store |
| HTTP client | fetch manual com token no header | axios + interceptor automático |
| Ícones | react-native-vector-icons (Ionicons) | lucide-react-native |
| Upload | react-native-image-picker | expo-image-picker |
| Build | Gradle/Xcode local | EAS Build (nuvem) |
| Backend | PHP legado | Django 6.0 + DRF + JWT |

---

## Estrutura de Arquivos

```
abase_mobile_new/
├── app.json                          # Configuração Expo (bundleId, assets, plugins)
├── eas.json                          # Profiles de build: development / preview / production
├── babel.config.js                   # babel-preset-expo + module-resolver (@/ alias)
├── tsconfig.json                     # paths: @/* → src/*
├── .env                              # EXPO_PUBLIC_API_BASE_URL
├── src/
│   ├── app/                          # Expo Router — roteamento por arquivo
│   │   ├── _layout.tsx               # Root: AuthProvider + Slot
│   │   ├── index.tsx                 # Redirect para /(auth)/splash
│   │   ├── (auth)/
│   │   │   ├── _layout.tsx           # Stack sem header
│   │   │   ├── splash.tsx            # Tela inicial / verificação de sessão
│   │   │   ├── login.tsx
│   │   │   ├── register.tsx
│   │   │   ├── forgot-password.tsx
│   │   │   └── reset-password.tsx
│   │   └── (app)/
│   │       ├── _layout.tsx           # Guard de autenticação (redireciona se sem token)
│   │       ├── espera.tsx            # Fila de espera
│   │       ├── cadastro-associado.tsx # Cadastro completo (maior tela, ~45KB original)
│   │       ├── atualizar-cadastro.tsx # Atualizar cadastro completo
│   │       ├── atualizar-dados-basicos.tsx # Atualizar dados básicos + CEP autocomplete
│   │       ├── pendencias-documentos.tsx   # Upload de documentos pendentes
│   │       ├── auxilio-emergencial.tsx     # Fluxo de auxílio emergencial (Pix)
│   │       └── (tabs)/
│   │           ├── _layout.tsx       # Tab bar + StatusBanners overlay
│   │           ├── index.tsx         # Home (saldo, próxima parcela)
│   │           ├── mensalidades.tsx  # Ciclos e parcelas
│   │           ├── beneficios.tsx    # Benefícios do associado
│   │           ├── antecipacao.tsx   # Histórico de antecipações
│   │           └── perfil.tsx        # Perfil + logout
│   ├── services/api/
│   │   ├── constants.ts              # BASE_URL + todos os ENDPOINTS
│   │   ├── client.ts                 # Instância axios + interceptor Bearer token
│   │   ├── authService.ts            # login, logout, me
│   │   ├── homeService.ts            # getHome (bootstrap)
│   │   ├── mensalidadesService.ts
│   │   ├── antecipacaoService.ts
│   │   ├── cadastroService.ts        # getCadastroShowMy, submitCadastroAssociadoBasico, submitReuploadBasico
│   │   ├── atualizarService.ts       # submitAtualizarBasico, checkCpfDuplicadoBasico
│   │   ├── pendenciasService.ts      # getIssuesMy, submitReupload
│   │   ├── auxilioDoisService.ts     # getAuxilioDoisStatus, createAuxilioDoisCharge, waitUntilPaid
│   │   └── esperaService.ts          # submitContato, getEsperaStatus
│   ├── context/
│   │   └── AuthContext.tsx           # {token, user, roles} no SecureStore
│   ├── components/
│   │   ├── ProgressBar.tsx           # Barra de progresso animada
│   │   ├── StatusBanners.tsx         # Banners "Complete cadastro" / "Em análise"
│   │   └── TabBar.tsx                # Tab bar customizada com SVGs
│   ├── types/
│   │   └── index.ts                  # Todos os tipos TypeScript
│   ├── utils/
│   │   └── format.ts                 # moneyBR, maskCpf, firstNameUpper, formatCpfCnpj
│   └── assets/
│       ├── icon.png                  # 1024×1024 (ícone do app)
│       ├── adaptive-icon.png         # Android adaptive icon
│       └── female.png                # Background das telas de auth
```

---

## Endpoints da API

Todos os endpoints do legado foram mantidos **exatamente iguais** (compatibilidade com novo backend Django):

| Funcionalidade | Endpoint | Método |
|---|---|---|
| Login | `/api/login` | POST |
| Logout | `/api/logout` | POST |
| Home/Bootstrap | `/api/home` | GET |
| Me | `/api/me` | GET |
| Register | `/api/auth/register` | POST |
| Forgot password | `/api/auth/forgot-password` | POST |
| Reset password | `/api/auth/reset-password` | POST |
| Mensalidades | `/api/app/mensalidades` | GET |
| Antecipação | `/api/app/antecipacao/historico` | GET |
| Status A2 | `/api/associadodois/status` | GET |
| Cadastro (GET) | `/api/associadodois/cadastro` | GET |
| Cadastro (POST) | `/api/associadodois/cadastro` | POST |
| Check CPF | `/api/associadodois/check-cpf` | POST |
| Issues | `/api/associadodois/issues/my` | GET |
| Reupload docs | `/api/associadodois/reuploads` | POST |
| Atualizar básico | `/api/associadodois/atualizar-basico` | POST |
| Aceite termos | `/api/associadodois/aceite-termos` | POST |
| Contato espera | `/api/associadodois/contato` | POST |
| Auxílio2 status | `/api/associadodois/auxilio2/status` | GET |
| Auxílio2 resumo | `/api/associadodois/auxilio2/resumo` | GET |
| Auxílio2 charge | `/api/associadodois/auxilio2/charge-30` | POST |

Novos endpoints Django (v1):

| Funcionalidade | Endpoint |
|---|---|
| Me consolidado | `/api/v1/app/me/` |
| Pendências | `/api/v1/app/pendencias/` |
| Upload documento | `/api/v1/app/documentos/` |

---

## Decisões Técnicas

### `expo-secure-store` em vez de `AsyncStorage`
Armazena `{ token, user, roles }` com criptografia nativa. Limite de ~2KB no iOS, por isso o `bootstrap` (dados da home) **não** é armazenado — é re-fetchado via `GET /api/home` ao reabrir o app.

### Axios interceptor
```ts
// client.ts — injeta token automaticamente em todas as requisições
apiClient.interceptors.request.use(async (config) => {
  const token = await SecureStore.getItemAsync('@Abase:token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
```
Nenhum serviço precisa receber o token como parâmetro.

### `SelectField` customizado (substitui `@react-native-picker/picker`)
O `@react-native-picker/picker` não está disponível no Expo Managed. Foi criado um componente `SelectField` usando `Modal` + `FlatList` em todas as telas que precisam de select (cadastro, atualizar cadastro, atualizar dados básicos).

### `expo-image-picker` (substitui `react-native-image-picker`)
```ts
// Legado
const result = await launchImageLibrary({ mediaType: 'photo' });
const file = { uri, fileName, type };

// Novo
const result = await launchImageLibraryAsync({ mediaTypes: MediaTypeOptions.Images });
const file = { uri: asset.uri, name: asset.fileName ?? 'doc.jpg', type: asset.mimeType ?? 'image/jpeg' };
```
O `FormData.append(key, file)` permanece igual.

### Navegação (Expo Router)
```ts
// Legado
navigation.navigate('Home')
navigation.goBack()
route.params.token

// Novo
router.replace('/(app)/(tabs)/')
router.back()
useLocalSearchParams<{ token: string }>()
```

### Ícones (Ionicons → lucide-react-native)
| Ionicons (legado) | lucide-react-native (novo) |
|---|---|
| `person-outline` | `User` |
| `eye-outline` / `eye-off-outline` | `Eye` / `EyeOff` |
| `lock-closed-outline` | `Lock` |
| `log-out-outline` | `LogOut` |
| `chevron-back` | `ChevronLeft` |
| `document-text-outline` | `FileText` |

### Variáveis de ambiente
```ts
// Legado
import { API_URL } from '@env';  // react-native-dotenv

// Novo
process.env.EXPO_PUBLIC_API_BASE_URL  // prefixo EXPO_PUBLIC_ obrigatório
```

---

## Mudanças no Backend

### `backend/apps/associados/serializers.py`
Adicionado campo `mobile_sessions` no `AssociadoDetailSerializer`:

```python
from apps.accounts.models import MobileAccessToken

class AssociadoDetailSerializer(serializers.ModelSerializer):
    mobile_sessions = serializers.SerializerMethodField()

    def get_mobile_sessions(self, obj):
        user = getattr(obj, "user", None)
        if not user:
            return []
        qs = MobileAccessToken.objects.filter(
            user=user,
            revoked_at__isnull=True,
            deleted_at__isnull=True,
        ).order_by("-last_used_at")[:3]
        return [
            {"last_used_at": t.last_used_at, "is_active": t.is_active}
            for t in qs
        ]
```

### `apps/web/src/lib/api/types.ts`
```ts
// AssociadoDetail — campo adicionado
mobile_sessions?: { last_used_at: string | null; is_active: boolean }[];
```

### `apps/web/src/app/(dashboard)/associados/[id]/page.tsx`
Badge "App ativo" quando o associado tem sessão mobile ativa:
```tsx
{(associado.mobile_sessions ?? []).some((s) => s.is_active) && (
  <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-400">
    <SmartphoneIcon className="h-3 w-3" />
    App ativo
  </span>
)}
```

---

## EAS Build

### Projeto registrado
- **Owner:** `helciovenancio`
- **Project ID:** `6f760d38-1bec-4112-8471-99476fa4c13e`
- **Slug:** `abase-mobile`

### Comandos

```bash
cd abase_mobile_new

# Desenvolvimento (APK com dev client)
eas build --platform android --profile development

# Preview (APK para teste interno)
eas build --platform android --profile preview

# Produção (AAB para Google Play)
eas build --platform all --profile production
```

### Profiles (`eas.json`)
| Profile | Distribution | Android format | `autoIncrement` |
|---|---|---|---|
| `development` | internal | APK | não |
| `preview` | internal | APK | não |
| `production` | store | App Bundle (AAB) | sim |

---

## Problemas Encontrados e Soluções

### 1. `react@18.3.2` não existe no npm
**Erro:** `No matching version found for react@18.3.2`
**Solução:** Corrigido para `"react": "18.3.1"` no `package.json`.

### 2. Conflitos de peer deps no npm install
**Erro:** Expo 53 esperava React 19, projeto usava React 18
**Solução:** `npm install --legacy-peer-deps` em todos os installs.

### 3. `eas project:init` falhando sem deps instaladas
**Erro:** `Failed to resolve plugin for module "expo-router"`
**Solução:** Executar `npm install` antes do `eas project:init`.

### 4. `ajv@6` incompatível com expo-router
**Erro:** `Cannot find module 'ajv/dist/compile/codegen'`
**Solução:** `npm install ajv@8 --legacy-peer-deps`

### 5. Placeholder de `projectId` no `app.json`
**Erro:** `Invalid UUID appId`
**Solução:** Remover o placeholder `"YOUR_EAS_PROJECT_ID"` antes do `eas project:init`.

### 6. Projeto não existia no EAS
**Erro:** `Project does not exist: @helciovenancio/abase-mobile`
**Solução:** `eas project:init --non-interactive --force`

### 7. `Animated` importado de `'react'` (erro de digitação)
**Erro:** `Animated` não é exportado de `'react'`
**Solução:** Mover `Animated` e `Easing` para o import de `'react-native'` em `cadastro-associado.tsx`.

### 8. SDK incompatível com Expo Go instalado
**Erro:** `Project is incompatible with this version of Expo Go. The installed version is for SDK 54, project uses SDK 53.`
**Solução:** Upgrade completo de SDK 53 → SDK 54 (19 pacotes atualizados).

### 9. `react-native-worklets` não instalado (reanimated v4)
**Erro:** `Cannot find module 'react-native-worklets/plugin'`
**Causa:** `babel-preset-expo` do SDK 54 carrega automaticamente o plugin do reanimated, que na v4 requer `react-native-worklets` como dependência
**Solução:** `npm install react-native-worklets --legacy-peer-deps`

### 10. Plugin do reanimated no `babel.config.js`
**Erro:** Conflito ao ter `react-native-reanimated/plugin` manual + `babel-preset-expo` que já o inclui automaticamente no SDK 54
**Solução:** Remover `'react-native-reanimated/plugin'` do array `plugins` no `babel.config.js`.

### 11. Pasta `assets/` ausente na raiz
**Erro:** `ENOENT: no such file or directory, scandir '.../abase_mobile_new/assets'`
**Solução:** Criar pasta `assets/` vazia na raiz do projeto.

### 12. Diretórios temporários quebrados no `node_modules`
**Erros:**
- `node_modules/.expo-modules-core-jUMhSXnB/android/src/main/java/expo/modules/adapters/react/apploader`
- `node_modules/@react-native/.babel-preset-g8pWeDha/src`

**Causa:** Resíduos de instalações interrompidas durante o upgrade de SDK
**Solução:** `rm -rf node_modules/<diretório>` + `npm install --legacy-peer-deps`

### 13. `female.png` não copiado para `src/assets/`
**Erro:** `Unable to resolve "../../assets/female.png" from "src/app/(auth)/forgot-password.tsx"`
**Solução:** Copiar `female.png` do app legado para `src/assets/female.png`.

---

## Variáveis de Ambiente

Arquivo `.env` na raiz de `abase_mobile_new/`:

```env
EXPO_PUBLIC_API_BASE_URL=https://www.abasepiaui.com/api
```

O prefixo `EXPO_PUBLIC_` é obrigatório para que a variável fique disponível no bundle cliente (Metro bundler).

---

## Dependências Finais (SDK 54)

```json
{
  "expo": "~54.0.0",
  "expo-router": "~6.0.23",
  "react": "^19.1.0",
  "react-native": "^0.81.5",
  "expo-secure-store": "~15.0.8",
  "expo-image-picker": "~17.0.10",
  "expo-file-system": "~19.0.21",
  "expo-font": "~14.0.11",
  "expo-constants": "~18.0.13",
  "expo-linking": "~8.0.11",
  "expo-splash-screen": "~31.0.13",
  "expo-status-bar": "~3.0.9",
  "react-native-reanimated": "~4.1.1",
  "react-native-worklets": "^0.8.1",
  "react-native-gesture-handler": "~2.28.0",
  "react-native-safe-area-context": "~5.6.0",
  "react-native-screens": "~4.16.0",
  "react-native-svg": "^15.12.1",
  "axios": "^1.7.9",
  "lucide-react-native": "^0.475.0",
  "ajv": "^8.18.0"
}
```

---

## Como Executar Localmente

```bash
cd abase_mobile_new

# Instalar dependências
npm install --legacy-peer-deps

# Iniciar Metro Bundler
npx expo start

# Ou em porta específica
npx expo start --port 8082
```

Escanear o QR code com o app **Expo Go** (SDK 54) no Android ou iOS.
