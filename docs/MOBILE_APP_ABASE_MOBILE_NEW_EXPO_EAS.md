# App Mobile `abase_mobile_new` via Expo e EAS

## Objetivo
Documentar como abrir o app `abase_mobile_new` localmente via Expo e quais são os caminhos para gerar e enviar builds Android e iOS via EAS CLI, sem alterar o app nem o backend.

## Escopo desta análise
Análise feita em 31 de março de 2026 sobre o projeto em:

```text
/mnt/d/apps/abasev2/abasev2/abase_mobile_new
```

Pontos confirmados no estado atual:
- o app usa Expo Managed Workflow com Expo SDK 54
- o app usa Expo Router (`main: expo-router/entry`)
- não existem diretórios nativos `android/` ou `ios/` dentro de `abase_mobile_new`
- o projeto mobile não faz parte do `pnpm-workspace.yaml` do monorepo
- existe `package-lock.json` dentro do app, então o fluxo mais direto aqui é com `npm`
- a variável `EXPO_PUBLIC_API_BASE_URL` está definida tanto no `.env` local quanto nos profiles do `eas.json`
- o app já aponta para a API de produção em `https://abasepiaui.cloud/api/v1`
- o app tem `.npmrc` local com `legacy-peer-deps=true` para evitar `ERESOLVE` causado por peers web opcionais do ecossistema Expo Router
- o projeto EAS já está vinculado ao owner `helciovenancio` e ao `projectId` `6f760d38-1bec-4112-8471-99476fa4c13e`
- o monorepo agora possui `.easignore` na raiz e dentro do app para impedir que o EAS envie `backend`, `backups`, `anexos_legado`, `dumps_legado`, `.git` e `node_modules`

Conclusão prática:
- para abrir o app sem alterar a estrutura do projeto, use `expo start`
- evite `expo prebuild`, `expo run:android` e `expo run:ios`, porque esses comandos podem gerar ou atualizar código nativo

## Arquivos relevantes
- `abase_mobile_new/package.json`
- `abase_mobile_new/app.json`
- `abase_mobile_new/eas.json`
- `abase_mobile_new/.env`
- `abase_mobile_new/src/services/api/constants.ts`

## Configuração atual do app

### Identificação do app
- nome: `ABASE`
- slug: `abase-mobile`
- scheme: `abase`
- owner Expo: `helciovenancio`
- Android package: `br.org.abase.mobile`
- iOS bundle identifier: `br.org.abase.mobile`

### API configurada hoje
Valor atual usado localmente e nos builds EAS:

```dotenv
EXPO_PUBLIC_API_BASE_URL=https://abasepiaui.cloud/api/v1
```

Na prática:
- no desenvolvimento local via Expo, esse valor vem do arquivo `.env`
- no EAS Build, esse valor vem do `env` de cada profile no `eas.json`

### Dependências fixadas para compatibilidade com Expo SDK 54

As versões abaixo ficaram fixadas porque eram a origem do erro de `ERESOLVE` ao tentar preparar o APK:

- `react`: `19.1.0`
- `react-native`: `0.81.5`
- `react-native-worklets`: `0.5.1`
- `react-native-svg`: `15.12.1`
- `lucide-react-native`: `^1.7.0`
- `expo-updates`: `~29.0.16`

Validação local final:

```bash
cd /mnt/d/apps/abasev2/abasev2/abase_mobile_new
./node_modules/.bin/expo install --check
```

Resultado esperado:

```text
Dependencies are up to date
```

### Tamanho do pacote para EAS

O erro de upload grande não vinha do app em si; vinha do monorepo inteiro sendo compactado.

Maiores diretórios encontrados na raiz:

- `backups`: ~`8.6 GB`
- `anexos_legado`: ~`3.5 GB`
- `backend`: ~`2.4 GB`
- `.git`: ~`1.9 GB`

Depois do `.easignore`, uma prévia do pacote útil do app ficou em torno de:

- `3.5 MB` comprimido

## Pré-requisitos

### Para abrir localmente via Expo
- Node.js 20 ou superior
- npm
- Expo Go no celular, ou emulador Android, ou simulador iOS
- Android Studio se for usar emulador Android
- macOS com Xcode se for usar simulador iOS

### Para builds e envios via EAS
- `eas-cli` instalado
- login no Expo (`eas login`)
- conta Apple Developer para iOS
- acesso à Google Play Console para Android
- credenciais de assinatura configuradas ou delegadas ao EAS

Observação do ambiente analisado:
- o comando `eas --version` respondeu `eas-cli/18.4.0`

Se o comando `eas` não existir na máquina:

```bash
npm install -g eas-cli
```

Para validar autenticação antes de iniciar builds:

```bash
eas whoami
```

## Como abrir o app via Expo

### 1. Entrar na pasta correta
```bash
cd /mnt/d/apps/abasev2/abasev2/abase_mobile_new
```

No Windows, o caminho equivalente é:

```text
D:\apps\abasev2\abasev2\abase_mobile_new
```

### 2. Instalar dependências
Se for a primeira execução local ou se quiser garantir consistência com o `package-lock.json`:

```bash
npm ci
```

### 3. Conferir a variável de ambiente
O arquivo `.env` atual deve conter:

```dotenv
EXPO_PUBLIC_API_BASE_URL=https://abasepiaui.cloud/api/v1
```

### 4. Subir o servidor Expo
Use um destes comandos:

```bash
npm start
```

ou

```bash
npx expo start
```

### 5. Abrir o app
Opções práticas:
- Android físico: abrir o Expo Go e ler o QR Code
- Android emulador: com o emulador ligado, pressionar `a` no terminal do Expo
- iPhone físico: abrir o Expo Go e ler o QR Code
- iOS simulador: em macOS, pressionar `i` no terminal do Expo

## O que não usar se a exigência for não alterar o projeto
Evite estes comandos:

```bash
npm run android
npm run ios
expo run:android
expo run:ios
expo prebuild
```

Motivo:
- em `package.json`, `npm run android` e `npm run ios` chamam `expo run:*`
- esse fluxo sai do uso puramente managed e pode gerar `android/` e `ios/`
- isso contraria o objetivo de só abrir o app, sem alterar sua estrutura

## EAS Build já configurado

### Profiles atuais em `eas.json`

| Profile | Finalidade | Distribuição | Android | iOS |
|---|---|---|---|---|
| `development` | dev client | internal | APK | build interno |
| `test-apk` | APK de teste explícito | internal | APK | n/a |
| `preview` | teste interno | internal | APK | build interno |
| `production` | release de loja | store | AAB | build de loja |

Observações importantes:
- `development` tem `developmentClient: true`
- `test-apk` é o profile recomendado para gerar um APK de teste simples contra a API do servidor
- `preview` é o profile mais simples para QA interno
- `production` tem `autoIncrement: true`
- o bloco `android.buildType` só afeta Android; os mesmos profiles também podem ser usados em iOS

## Fluxo recomendado por cenário

### Cenário 1: abrir localmente e testar rápido
Use:

```bash
cd /mnt/d/apps/abasev2/abasev2/abase_mobile_new
npm start
```

Melhor para:
- validação funcional rápida
- leitura por Expo Go
- testes sem mexer em build nativo

### Cenário 2: gerar build interno Android para distribuição
Use:

```bash
cd /mnt/d/apps/abasev2/abasev2/abase_mobile_new
eas login
eas build --platform android --profile test-apk
```

Resultado esperado:
- build `APK`
- distribuição `internal`
- link de instalação para QA

Atalho equivalente pelo `package.json`:

```bash
cd /mnt/d/apps/abasev2/abasev2/abase_mobile_new
npm run eas:build:android:test
```

Esse é o comando recomendado quando a exigência é apenas gerar um APK de teste apontando para:

```text
https://abasepiaui.cloud/api/v1
```

Se o EAS CLI perguntar sobre configurar `EAS Update`:

- para gerar apenas um APK de teste, responda `No`
- isso não bloqueia o build Android interno
- a configuração de OTA updates pode ser feita depois, separadamente

### Cenário 3: gerar build interno iOS para distribuição
Use:

```bash
cd /mnt/d/apps/abasev2/abasev2/abase_mobile_new
eas login
eas build --platform ios --profile preview
```

Resultado esperado:
- build interno iOS
- distribuição controlada pelo fluxo Apple/EAS

Observação:
- para instalar em dispositivos iOS fora da App Store, normalmente será preciso conta Apple Developer e provisionamento adequado dos dispositivos

### Cenário 4: gerar release Android para Google Play
Use:

```bash
cd /mnt/d/apps/abasev2/abasev2/abase_mobile_new
eas login
eas build --platform android --profile production
```

Resultado esperado:
- artefato `AAB`
- incremento automático de versão de build no profile `production`

Depois do build, há dois caminhos:
- baixar o `.aab` e enviar manualmente pela Google Play Console
- enviar via CLI com `eas submit`

Exemplo via CLI:

```bash
eas submit --platform android --profile production
```

Pré-requisitos práticos:
- app já cadastrado na Play Console
- credenciais Android válidas
- service account da Play Console configurada se o envio for automatizado pelo EAS

### Cenário 5: gerar release iOS para App Store Connect
Use:

```bash
cd /mnt/d/apps/abasev2/abasev2/abase_mobile_new
eas login
eas build --platform ios --profile production
```

Resultado esperado:
- `.ipa` assinado para distribuição de loja
- incremento automático do `buildNumber` via `autoIncrement`

Depois do build, há dois caminhos:
- enviar manualmente para App Store Connect
- enviar via CLI com `eas submit`

Exemplo via CLI:

```bash
eas submit --platform ios --profile production
```

Pré-requisitos práticos:
- conta Apple Developer ativa
- app criado no App Store Connect com bundle identifier `br.org.abase.mobile`
- certificados e perfis de provisionamento resolvidos pelo EAS ou já existentes

## Sequência mínima recomendada para publicação

### Android
1. Validar localmente com `npm start`
2. Gerar build de teste com `eas build --platform android --profile preview`
3. Validar em aparelho real
4. Gerar release com `eas build --platform android --profile production`
5. Enviar o `.aab` para a Play Console manualmente ou com `eas submit`

### iOS
1. Validar localmente com Expo Go no iPhone ou, em macOS, com simulador
2. Gerar build interno com `eas build --platform ios --profile preview`
3. Validar em dispositivo provisionado ou fluxo interno Apple
4. Gerar release com `eas build --platform ios --profile production`
5. Enviar para App Store Connect manualmente ou com `eas submit`

## Riscos e cuidados
- não rode `expo run:*` se a meta for preservar o projeto sem gerar código nativo
- se mudar a URL da API para homologação, ajuste de forma consistente o `.env` local e o `env` do profile correspondente no `eas.json`
- `production` faz auto incremento de build; isso é bom para release, mas deve ser esperado no controle de versões
- iOS depende de credenciais Apple válidas mesmo que o build seja remoto no EAS
- Android e iOS compartilham o mesmo identificador lógico `br.org.abase.mobile`; não altere isso sem estratégia de publicação

## Resumo operacional
- abrir sem alterar estrutura: `npm start`
- build Android interno: `eas build --platform android --profile preview`
- build Android loja: `eas build --platform android --profile production`
- build iOS interno: `eas build --platform ios --profile preview`
- build iOS loja: `eas build --platform ios --profile production`
- envio CLI Android: `eas submit --platform android --profile production`
- envio CLI iOS: `eas submit --platform ios --profile production`
## Observacoes de Arquivo para EAS Build

- O projeto `abase_mobile_new` vive dentro de um monorepo muito maior.
- O build remoto da Expo pode tentar empacotar a raiz do repositório inteiro se não houver `.easignore` na raiz.
- Isso fazia o upload incluir diretórios gigantes como `backups/`, `anexos_legado/`, `backend/` e `.git/`, ultrapassando o limite de `2 GB`.
- O repositório agora tem um [`.easignore`](/mnt/d/apps/abasev2/abasev2/.easignore) na raiz com exclusões explícitas desses diretórios pesados.
- Não use um `.easignore` de raiz com `*` e exceções para o app; isso pode fazer o EAS montar um archive praticamente vazio e quebrar o build no hook final.
- O app também mantém um [`.easignore`](/mnt/d/apps/abasev2/abasev2/abase_mobile_new/.easignore) próprio para excluir `node_modules`, `.expo` e artefatos locais.

## Aviso de Versao do EAS

- O arquivo [eas.json](/mnt/d/apps/abasev2/abasev2/abase_mobile_new/eas.json) agora define `cli.appVersionSource = remote`.
- Isso remove o warning atual do EAS e mantém o versionamento alinhado com o serviço remoto da Expo.
