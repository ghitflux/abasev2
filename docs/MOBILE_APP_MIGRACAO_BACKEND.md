# Compatibilidade Mobile ABASE V2

## Objetivo
Preservar o app legado em `abase_mobile/Abase_mobile_legado/abasev2app` sem alterar visual, navegação, package IDs ou fluxo publicado, enquanto o backend novo continua operando normalmente em `/api/v1/*`.

## Diretriz adotada
- O contrato do app legado continua sendo a fonte de verdade.
- A web nova segue como regra de negócio e modelo de dados.
- O backend Django expõe uma facade compatível em `/api/*`.
- O app React Native CLI continua sem Expo nesta fase.

## O que foi implementado

### Autenticação legada
- `POST /api/login`
- `POST /api/logout`
- `GET /api/home`
- `GET /api/me`
- Modelo de sessão móvel dedicado: `MobileAccessToken`
- Autenticação bearer legada independente do JWT da web

### Autoatendimento público
- `POST /api/auth/register`
- `GET /api/auth/check-email`
- `POST /api/auth/forgot-password`
- `POST /api/auth/reset-password`
- Modelo de reset dedicado: `PasswordResetRequest`

### Compatibilidade do fluxo `associadodois`
- `GET /api/associadodois/status`
- `GET /api/associadodois/cadastro`
- `GET /api/associadodois/check-cpf`
- `POST /api/associadodois/atualizar-basico`
- `GET /api/associadodois/issues/my`
- `POST /api/associadodois/reuploads`
- `POST /api/associadodois/aceite-termos`
- `POST /api/associadodois/contato`
- `GET /api/associadodois/auxilio2/status`
- `GET /api/associadodois/auxilio2/resumo`
- `POST /api/associadodois/auxilio2/charge-30`

### Compatibilidade do fluxo `associado`
- `GET /api/associado/me`
- `GET /api/associado/a2/status`
- `GET /api/associado/termo-adesao`

### Compatibilidade app self-service
- `GET /api/app/mensalidades`
- `GET /api/app/mensalidades/ciclo`
- `GET /api/app/antecipacao/historico`
- `POST /api/app/client-log`

## Modelos adicionados para sustentar o contrato legado

### `accounts`
- `MobileAccessToken`
- `PasswordResetRequest`

### `associados`
- Novos campos em `Associado`:
  - `aceite_termos`
  - `termo_adesao_admin_path`
  - `termo_antecipacao_admin_path`
  - `contato_status`
  - `contato_updated_at`
  - `auxilio1_status`
  - `auxilio1_updated_at`
  - `auxilio2_status`
  - `auxilio2_updated_at`
- Novo modelo:
  - `Auxilio2Filiacao`

## Arquivos principais da implementação
- `backend/apps/accounts/mobile_legacy_auth.py`
- `backend/apps/accounts/mobile_legacy_views.py`
- `backend/apps/associados/mobile_legacy.py`
- `backend/apps/associados/mobile_legacy_views.py`
- `backend/config/urls.py`
- `backend/apps/accounts/migrations/0004_mobileaccesstoken_passwordresetrequest.py`
- `backend/apps/associados/migrations/0010_associado_aceite_termos_associado_auxilio1_status_and_more.py`

## Campos e semânticas preservadas
- Resposta de login compatível com `ok`, `token`, `token_type`, `user`, `roles`, `pessoa`, `vinculo_publico`, `dados_bancarios`, `contratos`, `resumo`, `termo_adesao`
- Alias de papel legado `ASSOCIADODOIS` preservado no bootstrap quando necessário
- Payloads compatíveis para `homeService`, `authService`, `mensalidadesService`, `antecipacaoService`, `cadastroService`, `pendenciasService`, `auxilioDoisService` e `esperaService`
- Abertura de termo por URL autenticada com `?token=...`

## Configuração operacional do backend

### Variáveis opcionais úteis
- `ABASE_HOME_WHATSAPP_GERAL`
- `ABASE_HOME_WHATSAPP_JURIDICO`
- `ABASE_MOBILE_AUXILIO2_PIX_COPIA_COLA`
- `ABASE_MOBILE_AUXILIO2_QR_IMAGE`

### Observação importante sobre `auxilio2`
O contrato do app foi preservado e o backend agora persiste `status`, `txid`, `chargeId`, `filiacaoId`, `pixCopiaECola` e `imagemQrcode`.

Sem integração PSP dedicada no repositório, o endpoint de cobrança usa:
- persistência real via `Auxilio2Filiacao`
- payload compatível para o app
- suporte opcional a PIX estático por variável de ambiente

Se a operação precisar de QR dinâmico de produção, a próxima etapa é plugar o PSP real no método de criação da cobrança, sem mexer no app.

## Rollout recomendado
1. Aplicar migrations.
2. Publicar o backend com a facade `/api/*`.
3. Manter o app legado apontando para `https://www.abasepiaui.com/api`.
4. Validar o build atual da loja contra o backend novo.
5. Só depois publicar nova versão mobile, se necessário.

## Validação executada
- `python -m compileall backend/apps/accounts backend/apps/associados backend/config`
- `python backend/manage.py check`
- Suite de contrato:

```bash
DATABASE_USER=root \
DATABASE_PASSWORD=abase \
DATABASE_HOST=127.0.0.1 \
TEST_DATABASE_USER=root \
TEST_DATABASE_PASSWORD=abase \
TEST_DATABASE_NAME=test_abase_v2_mobile_compat_full_2 \
DJANGO_SETTINGS_MODULE=config.settings.testing \
python backend/manage.py test apps.associados.tests.test_mobile_legacy_compatibility -v 2 --noinput
```

## Documentos complementares
- `docs/MOBILE_APP_AUDITORIA_CONTRATO.md`
- `docs/MOBILE_APP_WINDOWS_ANDROID_STUDIO.md`
