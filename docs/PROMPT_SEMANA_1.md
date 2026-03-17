# PROMPT SEMANA 1 — Setup, Infraestrutura e Fundação

> Prompt para Claude Code executar a Semana 1 do ABASE v2.
> Pré-requisito: CLAUDE.md do backend e frontend nas respectivas raízes.

## Contexto

ABASE v2: monorepo com pnpm workspaces, backend Django 6, frontend Next.js 16 (em apps/web/), MySQL 8, Redis 7, Celery. Docker Compose. Todos os 50 componentes shadcn/ui instalados de antemão, mais 14 componentes customizados.

---

## BLOCO 1 — Monorepo pnpm + Docker (Dia 1-2)

### Tarefa 1.1: Inicializar Monorepo com pnpm Workspaces

Criar estrutura completa:

```
abase-v2/
├── pnpm-workspace.yaml          # packages: ['apps/*', 'packages/*']
├── package.json                  # @abase/monorepo, private, packageManager: pnpm@9.15.0
├── .npmrc                        # strict-peer-dependencies=false, link-workspace-packages=true
├── .gitignore
├── Makefile
├── apps/
│   └── web/                      # @abase/web (Next.js 16)
│       ├── package.json
│       ├── next.config.ts
│       ├── kubb.config.ts
│       ├── components.json
│       ├── tsconfig.json          # extends @abase/tsconfig/nextjs.json
│       └── src/
├── packages/
│   ├── tsconfig/                  # @abase/tsconfig
│   │   ├── package.json
│   │   ├── base.json
│   │   └── nextjs.json
│   ├── eslint-config/             # @abase/eslint-config
│   │   └── package.json
│   └── shared-types/              # @abase/shared-types
│       ├── package.json
│       └── src/index.ts
├── backend/
├── docker/
├── docker-compose.yml
└── .env.example
```

Root package.json scripts:
```json
{
  "dev": "pnpm --filter @abase/web dev",
  "build": "pnpm -r build",
  "lint": "pnpm -r lint",
  "generate:api": "pnpm --filter @abase/web generate:api",
  "generate:schema": "cd backend && python manage.py spectacular --file schema.yaml --validate",
  "docker:up": "docker-compose up -d",
  "docker:down": "docker-compose down",
  "docker:build": "docker-compose up --build -d"
}
```

Inicializar e instalar:
```bash
pnpm install
```

### Tarefa 1.2: Configurar Next.js 16 em apps/web

```bash
cd apps/web
pnpm create next-app@latest . --typescript --tailwind --eslint --app --turbopack
```

Instalar dependências:
```bash
pnpm --filter @abase/web add @tanstack/react-query zustand zod react-hook-form @hookform/resolvers date-fns react-dropzone recharts next-themes sonner vaul cmdk embla-carousel-react lucide-react class-variance-authority clsx tailwind-merge tailwindcss-animate react-day-picker
pnpm --filter @abase/web add -D @kubb/core @kubb/plugin-oas @kubb/plugin-ts @kubb/plugin-client @kubb/plugin-react-query @kubb/plugin-zod
```

Inicializar shadcn/ui e instalar TODOS os 50 componentes de uma vez:
```bash
cd apps/web
pnpm dlx shadcn@latest init
pnpm dlx shadcn@latest add accordion alert alert-dialog aspect-ratio avatar badge breadcrumb button button-group calendar card carousel chart checkbox collapsible command context-menu dialog drawer dropdown-menu empty field hover-card input input-group input-otp item kbd label menubar native-select navigation-menu pagination popover progress radio-group resizable scroll-area select separator sheet sidebar skeleton slider sonner spinner switch table tabs textarea toggle toggle-group tooltip typography
```

### Tarefa 1.3: Backend Django 6

Criar projeto Django com estrutura modular. requirements/base.txt com: Django==6.0.2, djangorestframework==3.15.2, drf-spectacular==0.28.0, djangorestframework-simplejwt==5.4.0, django-filter==24.3, django-cors-headers==4.6.0, celery==5.4.0, django-celery-results==2.5.1, redis==5.2.0, mysqlclient==2.2.6, Pillow==11.1.0, openpyxl==3.1.5, gunicorn==23.0.0, python-decouple==3.8.

### Tarefa 1.4: Docker Compose

5 serviços: mysql (8.0), redis (7-alpine), backend (python:3.12-slim custom), celery (mesmo backend), frontend (node:22-alpine custom com pnpm). Frontend usa `pnpm --filter @abase/web dev`. Healthchecks em mysql e redis. Volumes nomeados.

**Validação**: `docker-compose up --build` → 5 serviços rodando. Backend em :8000/api/schema/, frontend em :3000.

---

## BLOCO 2 — Models + Migrations (Dia 3-4)

### Tarefa 2.1: Core

BaseModel (created_at, updated_at, deleted_at, SoftDeleteManager, AllObjectsManager), SingletonMeta.

### Tarefa 2.2: accounts

User (AbstractBaseUser, email como login), Role (5 roles), UserRole (M2M through).

### Tarefa 2.3: associados

Associado, Endereco (OneToOne), DadosBancarios (OneToOne), ContatoHistorico (OneToOne), Documento.

### Tarefa 2.4: contratos

Contrato (codigo gerado, valores DecimalField(10,2)), Ciclo (3 refs mensais), Parcela (numero 1-3).

### Tarefa 2.5: esteira

EsteiraItem, Transicao, Pendencia.

### Tarefa 2.6: importacao (CRUCIAL)

**ArquivoRetorno**: arquivo_nome, arquivo_url, formato (csv/xlsx), orgao_origem, competencia (DATE), total_registros, processados, nao_encontrados, erros, status (pendente/processando/concluido/erro), resultado_resumo (JSONField), uploaded_by (FK User), processado_em.

**ArquivoRetornoItem**: arquivo_retorno (FK), linha_numero, cpf_cnpj, matricula_servidor, nome_servidor, competencia (varchar 7), valor_descontado (Decimal), status_desconto (efetivado/rejeitado/cancelado/pendente), motivo_rejeicao (text null), associado (FK null), parcela (FK null), processado (bool), resultado_processamento (baixa_efetuada/nao_descontado/nao_encontrado/erro/ciclo_aberto), observacao.

**ImportacaoLog**: arquivo_retorno (FK), tipo (upload/parse/validacao/reconciliacao/baixa/erro), mensagem, dados (JSONField null).

### Tarefa 2.7: demais apps

refinanciamento (Refinanciamento, Comprovante), tesouraria (Confirmacao).

### Tarefa 2.8: Migrations + Fixtures

```bash
python manage.py makemigrations accounts associados contratos esteira refinanciamento tesouraria importacao relatorios
python manage.py migrate
python manage.py loaddata roles
```

**Validação**: showmigrations OK, fixtures carregam, banco abase_v2 com todas as tabelas.

---

## BLOCO 3 — Auth + Componentes Customizados (Dia 5-6)

### Tarefa 3.1: JWT Endpoints Backend

LoginSerializer, RefreshSerializer, UserSerializer. Views: login, refresh, logout, me. Permissions: IsAgente, IsAnalista, IsCoordenador, IsTesoureiro, IsAdmin.

### Tarefa 3.2: Auth Frontend

proxy.ts (intercepta requests), auth-store.ts (Zustand), use-auth.ts, use-permissions.ts, login page.

### Tarefa 3.3: Criar os 14 Componentes Customizados

Criar em `apps/web/src/components/custom/`:

**date-picker.tsx**: Popover + Calendar + date-fns pt-BR. Exibe "11 de mar. de 2026".

**date-range-picker.tsx**: Dois calendários para seleção de período.

**time-picker.tsx**: Input HH:MM com máscara e validação 00:00-23:59.

**date-time-picker.tsx**: DatePicker + TimePicker combinados. Retorna ISO string.

**searchable-select.tsx**: Command + Popover. Filtra opções com busca. Props: options, value, onChange.

**multi-select.tsx**: Command + Badge tags. Seleção múltipla com badges removíveis.

**input-currency.tsx**: Máscara R$ X.XXX,XX. Aceita só números. Armazena como number.

**input-cpf-cnpj.tsx**: Máscara dinâmica CPF ou CNPJ. Valida dígitos verificadores.

**input-phone.tsx**: Máscara (XX) XXXXX-XXXX.

**input-cep.tsx**: Máscara XXXXX-XXX + fetch ViaCEP.

**dropdown-actions.tsx**: DropdownMenu para coluna Ações de tabelas. Ícone MoreHorizontal.

**file-upload-dropzone.tsx**: react-dropzone. Drag-and-drop. accept: csv/xlsx. isProcessing state.

**calendar-competencia.tsx**: MonthPicker (mês/ano). Grid de meses em Popover. Navega entre anos.

**status-badge.tsx**: Badge com mapeamento de cores por status (verde/amarelo/vermelho/cinza/azul).

Criar também `src/lib/masks.ts` com funções: maskCPF, maskCNPJ, maskCPFCNPJ, maskPhone, maskCEP, maskCurrency, unmaskCurrency, validateCPF, validateCNPJ.

**Validação**: Cada componente renderiza isoladamente, aceita props documentadas, aplica máscaras corretamente.

---

## BLOCO 4 — Layout Base (Dia 7)

### Tarefa 4.1: Layout Principal

`(dashboard)/layout.tsx` com SidebarProvider, Header, main area, AuthGuard, renderização de sidebar por role.

### Tarefa 4.2: Sidebar

Ícones Lucide. Item ativo com background laranja. Submenus expansíveis. Botão Sair. Versão mobile (Sheet). Navegação condicional por role.

### Tarefa 4.3: Header

Busca global, Filtros Avançados + data, notificação, avatar + nome + role com DropdownMenu.

### Tarefa 4.4: Shared Components

StatsCard (título, valor, variação %), DataTable (sorting, paginação, row expandível), FilterAdvanced (Sheet lateral), ExportButton (dropdown CSV/PDF/Excel), EmptyState.

**Validação**: Login funcional end-to-end. Sidebar renderiza por role. Header com data. Navegação OK. Responsivo.

---

## Checklist Semana 1

- [ ] pnpm-workspace.yaml configurado com apps/* e packages/*
- [ ] Root package.json com packageManager: pnpm@9.15.0
- [ ] .npmrc com link-workspace-packages=true
- [ ] @abase/tsconfig, @abase/eslint-config, @abase/shared-types criados
- [ ] Docker Compose: 5 serviços rodando
- [ ] MySQL 8 com banco abase_v2
- [ ] Django 6 respondendo em /api/schema/
- [ ] Next.js 16 em :3000
- [ ] TODOS os 50 componentes shadcn/ui instalados
- [ ] 14 componentes customizados criados e testáveis
- [ ] Todos os models incluindo ArquivoRetorno, ArquivoRetornoItem, ImportacaoLog
- [ ] Migrations aplicadas + fixture de roles
- [ ] JWT login/refresh/logout funcionando
- [ ] proxy.ts interceptando no frontend
- [ ] Sidebar condicional por role
- [ ] Componentes shared (StatsCard, DataTable, etc.)
- [ ] Kubb configurado e gerando código
