# Próximos Passos - ABASE v2

## Status Atual (Outubro 2025)

### ✅ Concluído

**Infraestrutura (Bloco 1)**
- [x] Monorepo configurado (pnpm + Turborepo)
- [x] Backend Django 5.0 + Django Ninja funcionando
- [x] Frontend Next.js 14 + Turbopack funcionando
- [x] PostgreSQL + Redis rodando via Docker
- [x] Design System @abase/ui + Storybook
- [x] Virtual environment Python configurado
- [x] Migrações aplicadas

**Backend - Fase 2 (Bloco 2)**
- [x] Models: Associado, Cadastro, EventLog
- [x] Estrutura de autenticação (Strategy Pattern)
- [x] Routers definidos (auth, cadastros, análise, tesouraria, SSE)
- [x] Redis configurado para cache/sessões
- [x] Celery configurado para jobs assíncronos
- [x] Job de importação CSV de associados
- [x] Exception handlers globais

### 🔧 Erros Corrigidos

1. **ModuleNotFoundError: 'ninja'** - ✅ Resolvido
   - Criado venv em `apps/api/`
   - Instaladas todas as dependências
   - Atualizado psycopg de 3.1.18 para 3.2.9

2. **Arquivo .env ausente** - ✅ Resolvido
   - Criado `.env.local` a partir de `.env.example`

3. **Migrações não aplicadas** - ✅ Resolvido
   - Executado `python manage.py migrate` com sucesso

4. **Validação dos servidores** - ✅ Resolvido
   - API: Django rodando sem erros
   - Web: Next.js compilando
   - Storybook: Build gerado com sucesso

---

## 🎯 BLOCO 3: Autenticação e Autorização

### Objetivo
Implementar o fluxo completo de autenticação com múltiplas estratégias (OIDC, Local, LDAP) e sistema de autorização baseado em roles.

### Tarefas Backend

#### 1. Implementar Lógica de Autenticação OIDC
**Arquivo**: `apps/api/api/v1/auth_router.py`

```python
# Endpoints a implementar:
- POST /api/v1/auth/oidc/callback
  - Validar code do provider
  - Trocar por tokens
  - Criar/atualizar usuário
  - Gerar JWT + Refresh Token
  - Armazenar no Redis
  - Retornar cookies httpOnly

- POST /api/v1/auth/refresh
  - Validar refresh token
  - Verificar blacklist no Redis
  - Gerar novo access token
  - Atualizar cookie

- POST /api/v1/auth/logout
  - Invalidar tokens
  - Adicionar à blacklist no Redis
  - Limpar cookies

- GET /api/v1/auth/me
  - Retornar dados do usuário autenticado
  - Validar JWT
```

**Dependências**:
- Configurar provider OIDC (Keycloak, Auth0, etc)
- Implementar `OIDCStrategy` em `core/auth/strategies.py`
- Usar `AuthenticationManager` Singleton

#### 2. Sistema de JWT + Refresh Token
**Arquivo**: `core/auth/managers.py`

```python
# Funcionalidades:
- generate_access_token(user) -> str
- generate_refresh_token(user) -> str
- validate_access_token(token) -> User
- validate_refresh_token(token) -> User
- blacklist_token(token) -> None
- is_blacklisted(token) -> bool

# Redis keys:
- access_token:{user_id} - TTL 15 min
- refresh_token:{user_id} - TTL 7 dias
- blacklist:{token_hash} - TTL do token original
```

#### 3. Middleware de Autenticação
**Novo arquivo**: `api/middleware/auth_middleware.py`

```python
# Funcionalidades:
- Ler JWT do header Authorization ou cookie
- Validar token
- Carregar usuário no request
- Bloquear requisições não autenticadas (exceto whitelist)
- Rate limiting por usuário
```

#### 4. Sistema de Permissões (RBAC)
**Arquivo**: `core/auth/permissions.py`

```python
# Roles:
- ADMIN: acesso total
- ANALISTA: aprovar/pendenciar/cancelar cadastros
- TESOUREIRO: registrar pagamentos, gerar contratos
- ASSOCIADO: criar e visualizar próprios cadastros

# Decoradores:
@require_role("ADMIN")
@require_permission("cadastros.aprovar")
@require_authenticated()
```

#### 5. Lockout e Rate Limiting
**Arquivo**: `core/auth/security.py`

```python
# Funcionalidades:
- track_failed_login(username) -> int
- is_locked_out(username) -> bool
- unlock_account(username) -> None
- rate_limit(user_id, endpoint) -> bool

# Configurações em fase2.py:
MAX_FAILED_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_MINUTES = 30
RATE_LIMIT_PER_MINUTE = 60
```

#### 6. Event Logging
**Usar**: `core/models/event_log.py`

```python
# Registrar eventos:
- LOGIN_SUCCESS
- LOGIN_FAILED
- LOGOUT
- TOKEN_REFRESHED
- TOKEN_BLACKLISTED
- ACCOUNT_LOCKED
- PASSWORD_CHANGED
```

### Tarefas Frontend

#### 1. Páginas de Autenticação
**Criar**:
- `apps/web/src/app/login/page.tsx` - Página de login
- `apps/web/src/app/auth/callback/page.tsx` - Callback OIDC
- `apps/web/src/app/auth/logout/page.tsx` - Logout

#### 2. Client de API
**Novo**: `apps/web/src/lib/api-client.ts`

```typescript
// Funcionalidades:
- fetch wrapper com JWT automático
- Refresh token automático em 401
- Redirect para login se não autenticado
- Toast de erros globais
```

#### 3. Context de Autenticação
**Novo**: `apps/web/src/contexts/AuthContext.tsx`

```typescript
// Estado:
- user: User | null
- isAuthenticated: boolean
- isLoading: boolean
- login(redirectUri?)
- logout()
- refreshToken()
```

#### 4. Rotas Protegidas
**Novo**: `apps/web/src/components/auth/ProtectedRoute.tsx`

```typescript
// HOC ou wrapper para proteger páginas
// Verificar autenticação
// Verificar permissões
// Redirect se não autorizado
```

#### 5. Componentes de UI
**Adicionar em** `packages/ui/src/components/`:
- `LoginForm.tsx` - Formulário de login
- `UserMenu.tsx` - Menu do usuário logado
- `PermissionGate.tsx` - Renderizar baseado em permissões

---

## 🎯 BLOCO 4: Fluxo de Cadastros

### Objetivo
Implementar o fluxo completo: criação → submissão → análise → tesouraria → conclusão

### Tarefas Backend

#### 1. Service de Cadastros
**Ampliar**: `core/services/cadastro_service.py`

```python
# Métodos:
- create_associado(data)
- create_cadastro(associado_id, data)
- submit_cadastro(cadastro_id, user)
- aprovar_cadastro(cadastro_id, analista, observacoes)
- pendenciar_cadastro(cadastro_id, analista, pendencias)
- cancelar_cadastro(cadastro_id, analista, motivo)
```

#### 2. Service de Tesouraria
**Novo**: `core/services/tesouraria_service.py`

```python
# Métodos:
- registrar_pagamento(cadastro_id, data)
- upload_comprovante(cadastro_id, file)
- enviar_nuvideo(cadastro_id)
- gerar_contrato_pdf(cadastro_id)
- assinar_contrato(cadastro_id, assinatura_id)
- concluir_cadastro(cadastro_id)
```

#### 3. Upload de Arquivos
**Novo**: `infrastructure/storage/uploader.py`

```python
# Funcionalidades:
- upload_file(file, tipo, entity_id) -> str (URL)
- delete_file(url) -> None
- Validar tipo e tamanho
- Sanitizar nome
- Organizar por pastas
```

#### 4. Integração NuVideo
**Implementar**: `infrastructure/nuvideo/client.py`

```python
# Funcionalidades:
- create_document(data) -> document_id
- send_for_signature(document_id, signers) -> signing_url
- check_status(document_id) -> status
- download_signed(document_id) -> bytes
```

#### 5. Geração de PDFs
**Implementar**: `infrastructure/pdf/generator.py`

```python
# Funcionalidades:
- generate_contrato(cadastro) -> bytes
- Templates com Jinja2 ou reportlab
- Incluir dados do cadastro
- QR Code para verificação
```

#### 6. SSE Real-Time
**Ampliar**: `api/v1/sse_router.py`

```python
# Eventos a publicar:
- CADASTRO_CRIADO
- CADASTRO_SUBMETIDO
- CADASTRO_APROVADO
- CADASTRO_PENDENTE
- CADASTRO_CANCELADO
- PAGAMENTO_RECEBIDO
- CONTRATO_GERADO
- CONTRATO_ASSINADO
- CADASTRO_CONCLUIDO
```

### Tarefas Frontend

#### 1. Formulário de Associado
**Criar**: `apps/web/src/app/associados/novo/page.tsx`
- Formulário multi-step
- Validação client-side
- Preview antes de salvar

#### 2. Formulário de Cadastro
**Criar**: `apps/web/src/app/cadastros/novo/page.tsx`
- Upload de documentos
- Múltiplos dependentes
- Cálculo de valores

#### 3. Dashboard de Análise
**Criar**: `apps/web/src/app/analise/page.tsx`
- Lista de cadastros pendentes
- Filtros por status, data, valor
- Ações: aprovar, pendenciar, cancelar

#### 4. Dashboard de Tesouraria
**Criar**: `apps/web/src/app/tesouraria/page.tsx`
- Cadastros aprovados
- Registrar pagamentos
- Gerenciar comprovantes
- Enviar para assinatura

#### 5. SSE Client
**Criar**: `apps/web/src/hooks/useSSE.ts`

```typescript
// Hook para consumir eventos SSE
const { events, isConnected } = useSSE();

useEffect(() => {
  events.on('CADASTRO_CRIADO', (data) => {
    // Atualizar lista
    // Mostrar toast
  });
}, [events]);
```

#### 6. Componentes UI Avançados
**Adicionar em** `packages/ui/`:
- `MultiStepForm.tsx` - Formulário multi-etapas
- `FileUpload.tsx` - Upload com preview
- `StatusBadge.tsx` - Badge de status
- `Timeline.tsx` - Timeline de eventos
- `SignatureCanvas.tsx` - Canvas para assinatura

---

## 🎯 BLOCO 5: Relatórios e Dashboard

### Backend
- Endpoints de relatórios em `api/v1/relatorios_router.py`
- Exportação Excel/PDF
- Filtros avançados
- Agregações e estatísticas

### Frontend
- Dashboard administrativo
- Gráficos com Recharts ou Victory
- Exportação de relatórios
- Calendário de eventos

---

## 📋 Ordem de Execução Recomendada

1. **Semana 1-2: Autenticação Backend**
   - Implementar OIDCStrategy
   - JWT + Refresh Token
   - Middleware de auth
   - Permissões RBAC

2. **Semana 3: Autenticação Frontend**
   - Páginas de login/callback
   - AuthContext
   - API client com tokens
   - Rotas protegidas

3. **Semana 4-5: Fluxo de Cadastros Backend**
   - Services de cadastro e tesouraria
   - Upload de arquivos
   - Integração NuVideo
   - Geração de PDFs

4. **Semana 6-7: Fluxo de Cadastros Frontend**
   - Formulários de associado e cadastro
   - Dashboards de análise e tesouraria
   - SSE client
   - Componentes UI avançados

5. **Semana 8: Relatórios**
   - Backend: endpoints e exportação
   - Frontend: dashboard e gráficos

6. **Semana 9-10: Testes e Refinamento**
   - Testes unitários
   - Testes de integração
   - Testes E2E
   - Correção de bugs
   - Documentação

---

## 🛠️ Ferramentas e Bibliotecas Adicionais

### Backend
- `PyJWT` - Já instalado ✅
- `httpx` - Já instalado ✅ (para OIDC)
- `Pillow` - Para manipulação de imagens
- `reportlab` ou `weasyprint` - Geração de PDFs
- `pytest` + `pytest-django` - Testes

### Frontend
- `@tanstack/react-query` - Cache e fetch de dados
- `react-hook-form` - Formulários complexos
- `zod` - Já instalado ✅ (validação)
- `recharts` - Gráficos
- `date-fns` - Manipulação de datas
- `@testing-library/react` - Testes

---

## 📝 Checklist de Validação

### Antes de Iniciar Bloco 3
- [ ] API Django rodando sem erros
- [ ] Migrations aplicadas
- [ ] PostgreSQL e Redis conectados
- [ ] Frontend compilando
- [ ] Storybook funcionando
- [ ] CLAUDE.md atualizado
- [ ] README.md atualizado

### Durante Desenvolvimento
- [ ] Commits frequentes e atômicos
- [ ] Testes para cada funcionalidade
- [ ] Documentação inline (docstrings/JSDoc)
- [ ] Code review entre desenvolvedores
- [ ] Manter CLAUDE.md atualizado

### Antes de Deploy
- [ ] Todos os testes passando
- [ ] Sem warnings no build
- [ ] Documentação completa
- [ ] Variáveis de ambiente documentadas
- [ ] Docker compose funcionando
- [ ] Migrations testadas em prod-like

---

## 🚀 Como Começar o Bloco 3

```bash
# 1. Garantir que tudo está funcionando
cd apps/api
source venv/bin/activate  # Windows: venv\Scripts\activate
python manage.py check
python manage.py runserver

# 2. Criar branch para nova feature
git checkout -b feature/bloco-3-autenticacao

# 3. Começar pela implementação da OIDCStrategy
# Editar: apps/api/core/auth/strategies.py

# 4. Testar iterativamente
python manage.py shell
>>> from core.auth.strategies import OIDCStrategy
>>> strategy = OIDCStrategy()
>>> # testar métodos

# 5. Implementar endpoints
# Editar: apps/api/api/v1/auth_router.py

# 6. Testar manualmente via curl ou Postman
curl http://localhost:8000/api/v1/health

# 7. Adicionar testes unitários
# Criar: apps/api/tests/test_auth.py

# 8. Commit e push
git add .
git commit -m "feat: implementa OIDCStrategy e endpoints de autenticação"
git push origin feature/bloco-3-autenticacao
```

---

## 📞 Suporte

- Documentação: Ver [.claude/CLAUDE.md](.claude/CLAUDE.md)
- Troubleshooting: Ver [README.md](README.md)
- Arquitetura: Ver [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
