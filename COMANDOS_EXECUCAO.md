# Comandos para Executar a Aplicação

## ✅ Correções Realizadas

### 1. API (FastAPI) - `apps/api/app/events/__init__.py`
- ✅ Corrigido import de `fastapi_sse` para `sse-starlette`
- ✅ Atualizado `sse_response` para `EventSourceResponse`
- ✅ Adicionado parâmetro `Request` no endpoint SSE
- ✅ Melhorado tratamento de desconexão de clientes
- ✅ Atualizado `requirements.txt` com dependência correta

### 2. Pacote UI (`@abase/ui`)
- ✅ Compilado com sucesso usando `tsup`
- ✅ Gerados arquivos `dist/index.js`, `dist/index.mjs` e types

### 3. Storybook - Stories Criadas
- ✅ **Button.stories.tsx** - Todas variantes, cores, tamanhos, ícones
- ✅ **StatusBadge.stories.tsx** - Status genéricos, de negócio e cadastro
- ✅ **DataTable.stories.tsx** - Tabelas com filtros, ações, paginação, seleção
- ✅ **Timeline.stories.tsx** - Timeline de eventos e StatusTimeline
- ✅ **FileUpload.stories.tsx** - Upload com progress, validações, tipos
- ✅ **FilterBuilder.stories.tsx** - Filtros avançados e quick filters
- ✅ **FormField.stories.tsx** - Todos os tipos de campos de formulário
- ✅ **MultiStepForm.stories.tsx** - Formulários multi-etapas
- ✅ **DocumentPreview.stories.tsx** - Preview de PDFs e imagens
- ✅ **DesignTokens.stories.tsx** - Cores, tipografia, espaçamentos, bordas, sombras, cards, tabelas

## 🔧 Comandos para Executar

### 1. Instalar Dependências Python (API)

```powershell
# Navegar até a pasta da API
cd apps/api

# Criar ambiente virtual
python -m venv venv

# Ativar ambiente virtual (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# OU Ativar ambiente virtual (Windows CMD)
.\venv\Scripts\activate.bat

# Instalar dependências
pip install -r requirements.txt
```

### 2. Verificar e Instalar Dependências do Frontend

```powershell
# Voltar para a raiz do projeto
cd ../..

# Instalar todas as dependências do monorepo
pnpm install

# Se houver erros de permissão, tente:
# - Fechar VSCode/editores
# - Executar PowerShell como Administrador
# - Executar: pnpm install --force
```

### 3. Iniciar a API (FastAPI)

```powershell
# Na pasta apps/api com venv ativado
cd apps/api
.\venv\Scripts\Activate.ps1

# Verificar se PostgreSQL e Redis estão rodando
docker ps

# Se não estiverem, iniciar:
docker-compose up -d postgres redis

# Aplicar migrações (se necessário)
python manage.py migrate

# OU se não houver manage.py, usar alembic:
alembic upgrade head

# Iniciar API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**API estará disponível em:** http://localhost:8000
**Documentação:** http://localhost:8000/docs

### 4. Iniciar o Frontend (Next.js)

```powershell
# Em um novo terminal, na raiz do projeto
cd apps/web

# Iniciar em modo desenvolvimento
pnpm dev
```

**Frontend estará disponível em:** http://localhost:3000

### 5. Iniciar o Storybook

```powershell
# Na raiz do projeto
pnpm storybook
```

**Storybook estará disponível em:** http://localhost:6006

## 📋 Checklist de Verificação

### API
- [ ] Docker com PostgreSQL rodando (`docker ps`)
- [ ] Docker com Redis rodando (`docker ps`)
- [ ] Ambiente virtual Python criado e ativado
- [ ] Dependências Python instaladas (`pip list`)
- [ ] Migrations aplicadas
- [ ] API iniciando sem erros em http://localhost:8000
- [ ] Documentação acessível em http://localhost:8000/docs

### Frontend
- [ ] Todas as dependências do pnpm instaladas
- [ ] Pacote `@abase/ui` compilado (`packages/ui/dist` existe)
- [ ] Aplicação iniciando sem erros em http://localhost:3000
- [ ] Páginas carregando corretamente

### Storybook
- [ ] Storybook iniciando sem erros
- [ ] Todos os componentes aparecendo:
  - Foundations/GettingStarted
  - Foundations/Design Tokens (Cores, Tipografia, Spacing, etc)
  - Components/Button
  - Components/StatusBadge
  - Components/DataTable
  - Components/Timeline
  - Components/FileUpload
  - Components/FilterBuilder
  - Components/FormField
  - Components/MultiStepForm
  - Components/DocumentPreview

## 🐛 Solução de Problemas

### Erro: "Module not found: Can't resolve 'lucide-react'"
```powershell
cd apps/web
pnpm add lucide-react
```

### Erro: "Module not found: pydantic"
```powershell
cd apps/api
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Erro: "EACCES: permission denied"
1. Feche todos os editores e terminais
2. Abra PowerShell como Administrador
3. Execute: `pnpm install --force`

### API não conecta ao PostgreSQL
```powershell
# Verificar se container está rodando
docker ps

# Se não estiver, iniciar
docker-compose up -d postgres

# Verificar logs
docker logs abasev2-postgres-1

# Testar conexão
docker exec -it abasev2-postgres-1 psql -U abase -d abase_v2
```

### Frontend com erro de hidratação
- Verifique se `@abase/ui` está compilado
- Tente limpar cache: `rm -rf apps/web/.next && pnpm dev`

## 📦 Estrutura de Arquivos Criados/Modificados

```
apps/api/
├── app/events/__init__.py          ✅ CORRIGIDO
└── requirements.txt                 ✅ ATUALIZADO (sse-starlette)

packages/ui/
└── dist/                            ✅ COMPILADO
    ├── index.js
    ├── index.mjs
    └── index.d.ts

storybook/stories/
├── Welcome.stories.tsx              (já existia)
├── Button.stories.tsx               ✅ CRIADO
├── StatusBadge.stories.tsx          ✅ CRIADO
├── DataTable.stories.tsx            ✅ CRIADO
├── Timeline.stories.tsx             ✅ CRIADO
├── FileUpload.stories.tsx           ✅ CRIADO
├── FilterBuilder.stories.tsx        ✅ CRIADO
├── FormField.stories.tsx            ✅ CRIADO
├── MultiStepForm.stories.tsx        ✅ CRIADO
├── DocumentPreview.stories.tsx      ✅ CRIADO
└── DesignTokens.stories.tsx         ✅ CRIADO
```

## 🚀 Próximos Passos

1. **Executar os comandos acima** para instalar dependências
2. **Iniciar os serviços** (API, Frontend, Storybook)
3. **Verificar** se tudo está funcionando sem erros
4. **Testar** as funcionalidades no navegador

---

**Última atualização:** 2025-10-15
**Status:** Correções concluídas, aguardando instalação de dependências
