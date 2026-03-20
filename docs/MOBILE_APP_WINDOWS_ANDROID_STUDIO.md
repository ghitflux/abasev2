# App Mobile no Windows e Android Studio

## Objetivo
Executar, validar e publicar o app legado em `abase_mobile/Abase_mobile_legado/abasev2app` no Windows sem alterar layout, navegação, package ID ou contrato de API.

## Caminho do projeto
No Windows, abra esta pasta:

```text
D:\apps\abasev2\abasev2\abase_mobile\Abase_mobile_legado\abasev2app
```

No WSL, o mesmo diretório é:

```text
/mnt/d/apps/abasev2/abasev2/abase_mobile/Abase_mobile_legado/abasev2app
```

## Pré-requisitos
- Node.js 20 ou superior
- Android Studio instalado no Windows
- Android SDK configurado no Android Studio
- Pelo menos um emulador Android criado no AVD Manager ou um aparelho Android com depuração USB habilitada
- JDK compatível com o Android Studio usado pelo projeto

## Abrir no Android Studio
1. Abra o Android Studio.
2. Escolha `Open`.
3. Selecione `D:\apps\abasev2\abasev2\abase_mobile\Abase_mobile_legado\abasev2app\android`.
4. Aguarde o sync do Gradle terminar.

## Configuração do `.env`
O app legado continua consumindo a facade compatível em `/api/*`. O `.env` deve apontar para o backend novo sem mudar os paths legados.

Exemplo mínimo:

```dotenv
API_URL=https://www.abasepiaui.com/api
LOGIN_API_URL=https://www.abasepiaui.com/api/login
LOGOUT_API_URL=https://www.abasepiaui.com/api/logout
HOME_API_URL=https://www.abasepiaui.com/api/home
ME_API_URL=https://www.abasepiaui.com/api/me
REGISTER_API_URL=https://www.abasepiaui.com/api/auth/register
APP_MENSALIDADES_URL=https://www.abasepiaui.com/api/app/mensalidades
ASSOCIADODOIS_CADASTRO_URL=https://www.abasepiaui.com/api/associadodois/cadastro
ATUALIZAR_BASICO_URL=https://www.abasepiaui.com/api/associadodois/atualizar-basico
ASSOCIADODOIS_ISSUES_MY_URL=https://www.abasepiaui.com/api/associadodois/issues/my
ASSOCIADODOIS_REUPLOADS_URL=https://www.abasepiaui.com/api/associadodois/reuploads
AUXILIO2_STATUS_URL=https://www.abasepiaui.com/api/associadodois/auxilio2/status
AUXILIO2_RESUMO_URL=https://www.abasepiaui.com/api/associadodois/auxilio2/resumo
AUXILIO2_CREATE_URL=https://www.abasepiaui.com/api/associadodois/auxilio2/charge-30
ASSOCIADODOIS_STATUS_URL=https://www.abasepiaui.com/api/associadodois/status
ASSOCIADODOIS_ACEITE_TERMOS_URL=https://www.abasepiaui.com/api/associadodois/aceite-termos
ASSOCIADODOIS_CONTATO_URL=https://www.abasepiaui.com/api/associadodois/contato
HOME_WHATSAPP_GERAL=5586981543302
HOME_WHATSAPP_JURIDICO=5586988763302
```

Regras práticas:
- Em produção, mantenha `https://www.abasepiaui.com/api`.
- Em homologação, mude apenas o domínio base. Não renomeie endpoints.
- Se o arquivo `.env` já existir, só ajuste o host quando necessário.

## Instalação de dependências
No PowerShell ou Prompt:

```powershell
cd D:\apps\abasev2\abasev2\abase_mobile\Abase_mobile_legado\abasev2app
npm ci
```

## Atalho recomendado no Windows
Para evitar repetir configuração de `JAVA_HOME`, limpeza e execução manual, rode o script abaixo:

```powershell
cd D:\apps\abasev2\abasev2\abase_mobile\Abase_mobile_legado\abasev2app
powershell -ExecutionPolicy Bypass -File .\run-android-windows.ps1
```

O script:
- detecta o Java do Android Studio
- exporta `JAVA_HOME` para a sessão
- cria um caminho curto em `D:\_abaseapp` para evitar erro de path length no Windows
- limpa `.gradle`, `app\build` e `app\.cxx`
- executa `gradlew clean`
- abre o Metro em outra janela
- roda `npm run android`

## Rodar no Android Studio e no emulador
1. Inicie um emulador pelo `Device Manager` do Android Studio.
2. Em um terminal, suba o Metro:

```powershell
cd D:\apps\abasev2\abasev2\abase_mobile\Abase_mobile_legado\abasev2app
npm start
```

3. Em outro terminal, instale o app no Android:

```powershell
cd D:\apps\abasev2\abasev2\abase_mobile\Abase_mobile_legado\abasev2app
npm run android
```

Alternativa pelo Gradle do Windows:

```powershell
cd D:\apps\abasev2\abasev2\abase_mobile\Abase_mobile_legado\abasev2app\android
.\gradlew.bat installDebug
```

## Rodar em aparelho físico Android
1. Ative `Opções do desenvolvedor` e `Depuração USB` no aparelho.
2. Conecte o aparelho ao Windows.
3. Confirme que ele aparece com:

```powershell
adb devices
```

4. Com o Metro ativo, rode:

```powershell
cd D:\apps\abasev2\abasev2\abase_mobile\Abase_mobile_legado\abasev2app
npm run android
```

## Conferências importantes antes de publicar
- `applicationId` permanece `com.abase.abasepi`
- `namespace` permanece `com.abase.abasepi`
- `versionCode` atual está em `8`
- `versionName` atual está em `1.0.7`
- `newArchEnabled` deve permanecer `false` neste projeto para evitar erro de path length no Windows
- O app deve continuar apontando para a facade compatível `/api/*`
- Não alterar assets, telas, textos ou árvore de navegação

Os campos de versão e package estão em `android/app/build.gradle`.

## Observação sobre build Android no Windows
Este projeto React Native CLI foi mantido com `newArchEnabled=false` em `android/gradle.properties`.

Motivo:
- evita falhas de `Filename longer than 260 characters` no CMake/Ninja
- o script `run-android-windows.ps1` também roda o projeto por um junction curto para reduzir o path efetivo do build
- reduz risco operacional no app legado
- não altera layout nem fluxo funcional do aplicativo

## Assinatura release
O projeto já espera estas variáveis Gradle:

```properties
ABASE_UPLOAD_STORE_FILE=seu-arquivo.keystore
ABASE_UPLOAD_STORE_PASSWORD=sua-senha
ABASE_UPLOAD_KEY_ALIAS=seu-alias
ABASE_UPLOAD_KEY_PASSWORD=sua-senha
```

Formas recomendadas de configurar:
- No arquivo `%USERPROFILE%\.gradle\gradle.properties`
- Ou no arquivo `android\gradle.properties` do projeto

Prática recomendada:
- Use a mesma upload key já cadastrada na Play Console
- Não troque `applicationId`
- Não gere uma nova chave sem confirmar que ela corresponde à app já publicada

## Gerar APK release
No Windows:

```powershell
cd D:\apps\abasev2\abasev2\abase_mobile\Abase_mobile_legado\abasev2app\android
.\gradlew.bat assembleRelease
```

Saída esperada:

```text
android\app\build\outputs\apk\release\app-release.apk
```

## Gerar AAB para Play Store
No Windows:

```powershell
cd D:\apps\abasev2\abasev2\abase_mobile\Abase_mobile_legado\abasev2app\android
.\gradlew.bat bundleRelease
```

Saída esperada:

```text
android\app\build\outputs\bundle\release\app-release.aab
```

## Incremento de versão
Antes de cada release para a loja:
- Aumente `versionCode` em `android/app/build.gradle`
- Atualize `versionName` para a versão pública desejada

Exemplo:

```gradle
versionCode 9
versionName "1.0.8"
```

Regra operacional:
- `versionCode` sempre sobe
- `versionName` comunica a versão visível para o usuário

## Fluxo recomendado de validação antes da submissão
1. Validar login com conta real.
2. Validar `home`.
3. Validar `mensalidades`.
4. Validar `cadastro` e atualização básica.
5. Validar pendências e reupload.
6. Validar aceite de termos.
7. Validar contato.
8. Validar `auxilio2`.
9. Gerar `bundleRelease`.
10. Subir o `.aab` na Play Console.

## Play Store
Para publicar atualização:
1. Gere o `.aab` assinado com a mesma upload key.
2. Entre na Play Console do app existente.
3. Crie uma nova release.
4. Envie `app-release.aab`.
5. Confirme que `versionCode` é maior que o release anterior.
6. Preencha notas da versão.
7. Envie para revisão.

## Observação sobre iOS
O build iOS continua dependendo de macOS com Xcode. O Windows não substitui a etapa de compilação e assinatura iOS.
