# Ajustes do `abase_mobile_new` em 2026-04-05

## Escopo

Este ajuste consolida as mudanças operacionais necessárias para publicar um novo build do app mobile apontando para a API oficial `https://abasepiaui.com/api/v1` e corrige a perda de autenticação no bootstrap inicial após o login.

## O que foi alterado

### 1. API oficial em `abasepiaui.com`

Os arquivos abaixo foram ajustados para usar a API oficial:

- `abase_mobile_new/src/services/api/constants.ts`
- `abase_mobile_new/eas.json`
- `abase_mobile_new/app.json`
- `abase_mobile_new/package.json`

Mudanças aplicadas:

- troca do host padrão de `https://abasepiaui.cloud/api/v1` para `https://abasepiaui.com/api/v1`
- atualização dos profiles do EAS para build Android e iOS apontando para a API oficial
- versionamento do app para `2.1.3`
- `ios.buildNumber = 213`
- `android.versionCode = 213`
- adição do profile `test-ios`

### 2. Remoção de barras finais nos endpoints

Em produção, a API oficial responde com `308` quando o app chama rotas como:

- `/api/v1/auth/login/`
- `/api/v1/app/me/`

Para evitar redirect em `POST` e inconsistência no React Native, os endpoints do app passaram a ser montados sem barra final.

Arquivo alterado:

- `abase_mobile_new/src/services/api/constants.ts`

Exemplos:

- `authLogin`: `/auth/login`
- `authRefresh`: `/auth/refresh`
- `appMe`: `/app/me`
- `appMensalidades`: `/app/mensalidades`

### 3. Correção da autenticação no bootstrap pós-login

O fluxo do app faz:

1. `POST /api/v1/auth/login`
2. persiste `access` e `refresh`
3. chama `GET /api/v1/app/me` para carregar o bootstrap do associado

O problema era que o request seguinte dependia de reler o token do `SecureStore` para montar o header `Authorization`. Em build nativo, esse primeiro request autenticado podia sair sem Bearer, gerando erro equivalente a "As credenciais de autenticação não foram fornecidas."

Arquivos alterados:

- `abase_mobile_new/src/services/api/client.ts`
- `abase_mobile_new/src/services/api/authService.ts`
- `abase_mobile_new/src/context/AuthContext.tsx`

Correção aplicada:

- criação de `volatileAccessToken` em memória no client HTTP
- sincronização do token em memória no login, refresh, reidratação de sessão e logout
- interceptador de request agora prioriza o token em memória e só cai para o `SecureStore` como fallback

## Validação executada

### Validação do fluxo local

Foi testado localmente o fluxo real:

1. `POST /api/v1/auth/login/`
2. armazenamento do `access`
3. `GET /api/v1/app/me/` com o Bearer recém-recebido

Resultado:

- login: `200`
- bootstrap `/app/me`: `200`

### Validação com credencial real na API oficial

Usuário testado:

- `JOAQUIM VIEIRA FILHO`
- matrícula: `0028029`
- CPF: `22808922353`

Resultado direto na API oficial:

- `POST https://abasepiaui.com/api/v1/auth/login` -> `200`
- a API retornou `access` e `refresh`

Isto confirma que a credencial do associado está válida e que o endpoint de login oficial responde corretamente.

## Pendência fora do app

Após o login na API oficial, as rotas autenticadas do servidor ainda responderam `401`:

- `GET /api/v1/auth/me`
- `GET /api/v1/app/mensalidades`

Resposta observada:

```json
{"detail":"As credenciais de autenticação não foram fornecidas."}
```

Isso indica problema de infraestrutura/proxy no servidor oficial, não no payload de login do app.

O ajuste relacionado a esse comportamento já existe no backend/deploy:

- commit `ef1e3ec`
- arquivo `deploy/hostinger/nginx/nginx.conf`

Enquanto esse deploy de servidor não for aplicado corretamente, o app pode autenticar no login, mas falhar ao carregar dados protegidos da API oficial.

## Resultado esperado após este commit

Quando um novo APK/IPA for gerado com estas mudanças:

- o app apontará para `abasepiaui.com`
- o login não usará mais endpoints com barra final
- o primeiro request autenticado do bootstrap usará o token em memória
- Android e iOS ficarão versionados como `2.1.3`
