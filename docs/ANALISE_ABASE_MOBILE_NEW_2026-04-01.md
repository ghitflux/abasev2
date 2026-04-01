# Analise do `abase_mobile_new` e alinhamento com o backend

Data: 01/04/2026

## Escopo validado

- Rotas `auth` usadas pelo app novo.
- Rotas `app` usadas pelo app novo.
- Fluxo real de cadastro do app:
  - criar conta
  - autenticar
  - enviar cadastro basico
  - enviar anexos iniciais
- Materializacao do `Associado` no mesmo banco consumido pelo sistema web.

## Endpoints do app novo vs backend atual

Base usada pelo app:

- `EXPO_PUBLIC_API_BASE_URL` ou fallback `https://abasepiaui.cloud/api/v1`

Endpoints consumidos pelo app:

- `POST /api/v1/auth/login/`
- `POST /api/v1/auth/refresh/`
- `POST /api/v1/auth/logout/`
- `GET /api/v1/auth/me/`
- `POST /api/v1/auth/register/`
- `POST /api/v1/auth/forgot-password/`
- `POST /api/v1/auth/reset-password/`
- `GET /api/v1/app/me/`
- `GET /api/v1/app/mensalidades/`
- `GET /api/v1/app/antecipacao/`
- `GET /api/v1/app/pendencias/`
- `POST /api/v1/app/pendencias/reuploads/`
- `POST /api/v1/app/documentos/`
- `GET /api/v1/app/cadastro/`
- `POST /api/v1/app/cadastro/`
- `GET /api/v1/app/cadastro/check-cpf/`
- `POST /api/v1/app/termos/aceite/`
- `POST /api/v1/app/contato/`
- `GET /api/v1/app/auxilio2/status/`
- `GET /api/v1/app/auxilio2/resumo/`
- `POST /api/v1/app/auxilio2/charge/`

Conclusao:

- Todas essas rotas existem no backend atual.
- A suite de compatibilidade mobile do backend cobre esse namespace `v1`.

## Achado real de desalinhamento

O app novo enviava o cadastro basico com nomes de campo modernos:

- `estado_civil`
- `profissao`
- `cargo`
- `logradouro`
- `numero`
- `complemento`
- `bairro`
- `cidade`
- `matricula_orgao`
- `banco`
- `agencia`
- `conta`
- `tipo_conta`
- `chave_pix`

O backend do `AppCadastroView` ainda delegava para `_resolve_or_create_associado()` esperando principalmente aliases legados:

- `marital_status`
- `profession`
- `address`
- `address_number`
- `complement`
- `neighborhood`
- `city`
- `matricula_servidor_publico`
- `bank_name`
- `bank_agency`
- `bank_account`
- `account_type`
- `pix_key`

Impacto antes da correcao:

- o `Associado` era criado/atualizado, mas varios campos do cadastro mobile novo podiam ser ignorados silenciosamente.
- o fluxo estava parcialmente alinhado, nao totalmente.

## Correcao aplicada

Arquivos alterados:

- [mobile_legacy_views.py](/mnt/d/apps/abasev2/abasev2/backend/apps/associados/mobile_legacy_views.py)
- [mobile_legacy.py](/mnt/d/apps/abasev2/abasev2/backend/apps/associados/mobile_legacy.py)
- [test_mobile_legacy_compatibility.py](/mnt/d/apps/abasev2/abasev2/backend/apps/associados/tests/test_mobile_legacy_compatibility.py)

O backend agora:

- aceita tanto os nomes modernos do `abase_mobile_new` quanto os aliases legados.
- persiste tambem o campo `cargo`.
- devolve no `GET /api/v1/app/cadastro/` tanto os nomes legados quanto os nomes modernos, para manter compatibilidade dupla.

## Validacao do fluxo real do app

Foi adicionada validacao automatizada cobrindo exatamente o fluxo do app novo:

1. `POST /api/v1/auth/register/`
2. `GET /api/v1/app/me/`
3. `POST /api/v1/app/cadastro/` com o payload real do `abase_mobile_new`
4. `POST /api/v1/app/pendencias/reuploads/` sem `issue_id`, como o onboarding do app faz
5. `GET /api/v1/app/cadastro/`

O teste prova que:

- a conta e criada com roles `ASSOCIADODOIS` e `ASSOCIADO`
- o `Associado` e materializado no banco principal
- o `Associado` fica vinculado ao `User`
- o status inicial do associado fica `EM_ANALISE`
- os campos de endereco, vinculo publico e dados bancarios enviados pelo app novo sao gravados corretamente
- os anexos iniciais enviados pelo app via `reuploads` sao recebidos e persistidos

## Resultado dos testes

Comando executado:

```bash
docker compose exec -T backend python manage.py test apps.associados.tests.test_mobile_legacy_compatibility -v 2
```

Resultado:

- `7` testes executados
- `7` testes OK

Checagem estatica do app:

```bash
./abase_mobile_new/node_modules/.bin/tsc --noEmit -p abase_mobile_new/tsconfig.json
```

Resultado:

- typecheck do `abase_mobile_new` concluido com sucesso

Inclui:

- login legado
- login `v1`
- endpoints principais `v1`
- cadastro `v1`
- reupload de documentos
- reset de senha
- novo teste do payload real do `abase_mobile_new`

## Comportamento esperado do cadastro mobile

Ponto importante:

- `POST /api/v1/auth/register/` cria a conta (`User`) e garante os perfis de autoatendimento.
- o `Associado` nao nasce no `register`.
- o `Associado` e criado ou atualizado quando o app envia `POST /api/v1/app/cadastro/`.

Esse comportamento esta correto para o fluxo atual do app.

## Conclusao final

Status final apos a correcao:

- `abase_mobile_new` esta alinhado com o backend atual no namespace `api/v1`.
- o fluxo de cadastro do app agora esta coberto e validado com o payload real do app novo.
- o cadastro pelo app gera o `Associado` normalmente no sistema web, porque grava no mesmo banco e no mesmo modelo `Associado` consumido pelo painel web.

## Observacao operacional

O badge de origem `Web` x `Mobile` do sistema web continua coerente com esse fluxo, porque o usuario criado pelo app recebe o papel `ASSOCIADODOIS`, que eh exatamente o sinal usado para identificar origem mobile.
