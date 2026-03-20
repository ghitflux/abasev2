# Matriz de Auditoria do Contrato Mobile

## Origem da verdade
- App legado: `abase_mobile/Abase_mobile_legado/abasev2app/services/api`
- Facade backend: `/api/*`
- Regra de negócio nova: modelos e serviços Django atuais

## Matriz por endpoint

| Fluxo | Endpoint legado | Payload esperado pelo app | Resposta compatível | Origem no backend novo | Adaptador | Status |
|---|---|---|---|---|---|---|
| Login | `POST /api/login` | `{login,password}` | `ok`, `token`, `user`, `roles`, bootstrap completo | `User`, `Associado`, `Contrato`, `Documento` | `apps.accounts.mobile_legacy_views.LegacyLoginView` | Implementado |
| Logout | `POST /api/logout` | bearer token | `{ok:true}` | `MobileAccessToken` | `apps.accounts.mobile_legacy_views.LegacyLogoutView` | Implementado |
| Home | `GET /api/home` | bearer token | `pessoa`, `vinculo_publico`, `dados_bancarios`, `contratos`, `resumo`, `termo_adesao`, `cadastro` | `Associado`, `Contrato`, `Parcela`, `Documento` | `apps.accounts.mobile_legacy_views.LegacyHomeView` + `apps.associados.mobile_legacy.build_bootstrap_payload` | Implementado |
| Me | `GET /api/me` | bearer token | `user`, `roles`, `agente`, `vinculo_publico`, `dados_bancarios`, `termo_adesao` | `User`, `Associado` | `apps.accounts.mobile_legacy_views.LegacyMeView` + `apps.associados.mobile_legacy.build_me_payload` | Implementado |
| Register | `POST /api/auth/register` | `name`, `email`, `password`, `password_confirmation`, `terms` | `ok`, `message`, `token`, `user`, `roles` | `User`, `Role`, `MobileAccessToken` | `apps.accounts.mobile_legacy_views.LegacyRegisterView` | Implementado |
| Check email | `GET /api/auth/check-email` | `?email=` | `exists`, `sources` | `User`, `Associado` | `apps.accounts.mobile_legacy_views.LegacyCheckEmailView` | Implementado |
| Forgot password | `POST /api/auth/forgot-password` | `{email}` | `{ok,message}` | `User`, `PasswordResetRequest` | `apps.accounts.mobile_legacy_views.LegacyForgotPasswordView` | Implementado |
| Reset password | `POST /api/auth/reset-password` | `email`, `token`, `password`, `password_confirmation` | `{ok,message}` | `User`, `PasswordResetRequest` | `apps.accounts.mobile_legacy_views.LegacyResetPasswordView` | Implementado |
| Perfil associado | `GET /api/associado/me` | bearer token | `pessoa`, `vinculo_publico`, `cadastro` | `Associado` | `apps.associados.mobile_legacy_views.LegacyAssociadoMeView` | Implementado |
| Status A2 | `GET /api/associado/a2/status` | bearer token | `exists`, `status`, `cadastro`, `permissions`, `auxilios`, `termos` | `Associado`, `Auxilio2Filiacao`, `Documento` | `apps.associados.mobile_legacy_views.LegacyAssociadoA2StatusView` | Implementado |
| Termo adesão | `GET /api/associado/termo-adesao` | bearer token ou `?token=` | redirect 302 para PDF | `Documento`, `Associado.termo_adesao_admin_path` | `apps.associados.mobile_legacy_views.LegacyAssociadoTermoAdesaoView` | Implementado |
| Status cadastro | `GET /api/associadodois/status` | bearer token | `exists`, `status`, `basic_complete`, `complete`, `cadastro`, `permissions`, `auxilios`, `aceite_termos`, `termos` | `Associado`, `Contrato`, `Documento`, `Auxilio2Filiacao` | `apps.associados.mobile_legacy_views.LegacyAssociadoDoisStatusView` | Implementado |
| Exibir cadastro | `GET /api/associadodois/cadastro` | bearer token | `exists`, `cadastro` | `Associado` | `apps.associados.mobile_legacy_views.LegacyAssociadoDoisCadastroView` | Implementado |
| Duplicidade CPF | `GET /api/associadodois/check-cpf` | `?cpf=` | `exists`, `data.full_name` | `Associado` | `apps.associados.mobile_legacy_views.LegacyAssociadoDoisCheckCpfView` | Implementado |
| Atualizar básico | `POST /api/associadodois/atualizar-basico` | multipart com campos flat e `payload` opcional | `{ok,message,cadastro}` | `Associado`, `User` | `apps.associados.mobile_legacy_views.LegacyAssociadoDoisAtualizarBasicoView` | Implementado |
| Pendências | `GET /api/associadodois/issues/my` | bearer token | `issues[]`, `cadastro` | `DocIssue`, `DocReupload`, fallback `Pendencia` | `apps.associados.mobile_legacy_views.LegacyAssociadoDoisIssuesView` | Implementado |
| Reupload | `POST /api/associadodois/reuploads` | multipart com arquivos e `associadodois_doc_issue_id` opcional | `{ok,message,saved_count}` | `Documento`, `DocReupload` | `apps.associados.mobile_legacy_views.LegacyAssociadoDoisReuploadsView` | Implementado |
| Aceite termos | `POST /api/associadodois/aceite-termos` | vazio | `{ok,aceite_termos}` | `Associado`, `Contrato.termos_web` | `apps.associados.mobile_legacy_views.LegacyAssociadoDoisAceiteTermosView` | Implementado |
| Solicitar contato | `POST /api/associadodois/contato` | vazio | `{ok,contato_status}` | `Associado`, `Contrato.contato_web` | `apps.associados.mobile_legacy_views.LegacyAssociadoDoisContatoView` | Implementado |
| Auxílio 2 status | `GET /api/associadodois/auxilio2/status` | bearer token | `status`, `complete`, `txid`, `valor`, `chargeId`, `filiacaoId`, `pixCopiaECola`, `imagemQrcode` | `Auxilio2Filiacao`, `Associado.auxilio2_status` | `apps.associados.mobile_legacy_views.LegacyAssociadoDoisAuxilio2StatusView` | Implementado |
| Auxílio 2 resumo | `GET /api/associadodois/auxilio2/resumo` | bearer token | mesmo contrato de status | `Auxilio2Filiacao`, `Associado.auxilio2_status` | `apps.associados.mobile_legacy_views.LegacyAssociadoDoisAuxilio2ResumoView` | Implementado |
| Auxílio 2 cobrança | `POST /api/associadodois/auxilio2/charge-30` | vazio | `ok`, `status`, `txid`, `chargeId`, `filiacaoId`, `pixCopiaECola`, `imagemQrcode` | `Auxilio2Filiacao` | `apps.associados.mobile_legacy_views.LegacyAssociadoDoisAuxilio2ChargeView` | Implementado |
| Mensalidades | `GET /api/app/mensalidades` | `cpf`, `ref_from`, `ref_to` opcionais | `{parcelas,resumo,proximo_ciclo,refinanciamento}` | `Parcela`, `Contrato`, snapshots do `Associado` | `apps.associados.mobile_legacy_views.LegacyMensalidadesView` | Implementado |
| Mensalidades ciclo | `GET /api/app/mensalidades/ciclo` | idem | mesmo contrato | `Parcela`, `Contrato` | `apps.associados.mobile_legacy_views.LegacyMensalidadesView` | Implementado |
| Antecipação histórico | `GET /api/app/antecipacao/historico` | bearer token | `{historico:[...]}` | `Associado.anticipations_json`, fallback `Pagamento` | `apps.associados.mobile_legacy_views.LegacyAntecipacaoHistoricoView` | Implementado |
| Client log | `POST /api/app/client-log` | JSON livre | `{ok:true}` | logging backend | `apps.associados.mobile_legacy_views.LegacyClientLogView` | Implementado |

## Cobertura por tela

| Tela / fluxo | Serviços do app | Endpoints cobertos | Status |
|---|---|---|---|
| Login | `authService` | `/api/login`, `/api/logout`, `/api/me`, `/api/home` | Implementado |
| Cadastro inicial | `registerService`, `cadastroService` | `/api/auth/register`, `/api/auth/check-email`, `/api/associadodois/check-cpf`, `/api/associadodois/atualizar-basico` | Implementado |
| Espera / status | `esperaService`, `cadastroService` | `/api/associadodois/status`, `/api/associadodois/cadastro`, `/api/associado/a2/status` | Implementado |
| Pendências | `pendenciasService` | `/api/associadodois/issues/my`, `/api/associadodois/reuploads` | Implementado |
| Perfil | `authService.getPerfilData` | `/api/home`, `/api/associado/me`, `/api/associado/termo-adesao`, `/api/associadodois/cadastro` | Implementado |
| Mensalidades | `mensalidadesService` | `/api/app/mensalidades`, `/api/app/mensalidades/ciclo`, `/api/me` | Implementado |
| Antecipação | `antecipacaoService` | `/api/app/antecipacao/historico`, fallback `/api/app/mensalidades` | Implementado |
| Auxílio 2 | `auxilioDoisService` | `/api/associadodois/auxilio2/status`, `/resumo`, `/charge-30` | Implementado |
| Termos e contato | `cadastroService` | `/api/associadodois/aceite-termos`, `/api/associadodois/contato`, `/api/associado/termo-adesao` | Implementado |
| Reset de senha | `forgotPasswordService` | `/api/auth/forgot-password`, `/api/auth/reset-password` | Implementado |

## Teste automatizado

Arquivo:
- `backend/apps/associados/tests/test_mobile_legacy_compatibility.py`

Fluxos cobertos:
- login legado e bootstrap completo
- consultas `/home`, `/me`, `/associado/*`, `/app/*`
- pendências e reuploads
- aceite de termos e solicitação de contato
- cobrança/status do auxílio 2
- register, check-email, update-basico e reset de senha

## Ponto de atenção conhecido
`/api/associadodois/auxilio2/charge-30` já persiste e responde no formato esperado pelo app, mas usa configuração estática opcional para `pixCopiaECola` e `imagemQrcode` quando não houver PSP real ligado no ambiente.
