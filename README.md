# ABASE Manager v2 - Sistema de Gestão de Associações

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![Django](https://img.shields.io/badge/Django-5.0-green)](https://www.djangoproject.com/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue)](https://www.typescriptlang.org/)

## 📋 Visão Geral

ABASE Manager v2 é um sistema completo de gestão de associações desenvolvido como monorepo moderno com arquitetura de microserviços. O sistema oferece funcionalidades completas para cadastro de associados, análise de documentos, processamento de pagamentos e geração de contratos com assinatura digital.

## 🏗️ Arquitetura

### Stack Tecnológico

**Backend:**
- Django 5.0 + Django Ninja (FastAPI-like)
- PostgreSQL 16 (via Docker)
- Redis 7 (cache, sessões, SSE)
- Celery (jobs assíncronos)
- JWT Authentication + OIDC
- RBAC (Role-Based Access Control)

**Frontend:**
- Next.js 14 (App Router) + Turbopack
- React 19 + TypeScript 5.0
- HeroUI + Tailwind CSS 4
- Design System @abase/ui
- Server-Sent Events (SSE)

**Infraestrutura:**
- Docker + Docker Compose
- pnpm workspaces + Turborepo
- Storybook para documentação de componentes

## 🚀 Status do Projeto

### ✅ **FASE 2 - CONCLUÍDA (100%)**

**Backend Completo:**
- ✅ Sistema de autenticação (OIDC + JWT)
- ✅ Middleware de autenticação com auto-validação
- ✅ RBAC com 5 roles e 23 permissões
- ✅ Rate limiting e lockout de contas
- ✅ Event logging para auditoria
- ✅ Todos os routers implementados (auth, cadastros, análise, tesouraria, SSE)
- ✅ Services layer completo
- ✅ Infraestrutura pronta (upload, NuVideo mock, geração de PDF)

**Frontend Completo:**
- ✅ API client com auto-refresh de tokens
- ✅ AuthContext com login/logout
- ✅ Páginas de autenticação (login, callback, dashboard)
- ✅ Rotas protegidas e gates de permissão
- ✅ Sistema de notificações (Toast)

### ✅ **FASE 3 - EM ANDAMENTO (40% Concluído)**

**Módulo Associados (100% Concluído):**
- ✅ Lista de associados com DataTable, filtros e busca
- ✅ Formulário multi-etapas (4 steps) com validação completa
- ✅ Páginas CRUD (criar, visualizar, editar)
- ✅ Validação de CPF, CEP, telefone
- ✅ Auto-complete de endereço via ViaCEP API
- ✅ Formatação automática de campos

**Módulo Cadastros (30% Concluído):**
- ✅ Lista de cadastros com filtros por status
- ✅ Badges de status com lógica de negócio
- ✅ Ações contextuais (submeter, editar, remover)
- ⏳ Formulário de cadastro com dependentes
- ⏳ Upload de documentos
- ⏳ Cálculo automático de valores

**Componentes UI Compartilhados (100% Concluído):**
- ✅ FileUpload com drag & drop e preview
- ✅ MultiStepForm com navegação e validação
- ✅ StatusBadge com status específicos do negócio
- ✅ Timeline para rastreamento de eventos
- ✅ DocumentPreview com modal fullscreen

**Utilitários (100% Concluído):**
- ✅ Formatters (CPF, CNPJ, telefone, moeda, data)
- ✅ Validators (CPF, CNPJ, email, telefone, CEP, senha)

## 📁 Estrutura do Projeto

```
abasev2/
├── apps/
│   ├── api/                    # Backend Django + Django Ninja
│   │   ├── config/            # Configurações Django
│   │   ├── core/              # Domínio e modelos
│   │   ├── api/               # Endpoints REST
│   │   ├── infrastructure/    # Integrações externas
│   │   └── tests/             # Testes
│   └── web/                   # Frontend Next.js
│       ├── src/app/           # App Router (pages)
│       ├── src/components/    # Componentes React
│       ├── src/contexts/      # Context providers
│       ├── src/hooks/         # Custom hooks
│       └── src/lib/           # Utilitários
├── packages/
│   ├── ui/                    # Design System @abase/ui
│   ├── config/                # Configurações compartilhadas
│   └── shared/                # Utils compartilhados
├── docker-compose.yml         # Orquestração de serviços
├── turbo.json                 # Configuração Turborepo
└── pnpm-workspace.yaml        # Configuração pnpm workspaces
```

## 🛠️ Instalação e Configuração

### Pré-requisitos

- Node.js 18+ e pnpm
- Python 3.11+ e pip
- Docker e Docker Compose
- Git

### Setup Inicial

```bash
# 1. Clone o repositório
git clone https://github.com/ghitflux/abasev2.git
cd abasev2

# 2. Instalar dependências do monorepo
pnpm install

# 3. Configurar ambiente
cp .env.example .env.local

# 4. Subir serviços de infraestrutura
docker-compose up -d postgres redis

# 5. Configurar backend
cd apps/api
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 6. Aplicar migrações
python manage.py migrate

# 7. Criar superusuário
python manage.py createsuperuser
```

### Desenvolvimento

```bash
# Todos os serviços (Turborepo)
pnpm dev

# Apenas API (Django)
cd apps/api
source venv/bin/activate
python manage.py runserver

# Apenas Web (Next.js)
cd apps/web
pnpm dev

# Storybook
pnpm storybook
```

## 🔐 Autenticação e Autorização

### Estratégias de Autenticação

- **OIDC**: Integração com provedores externos (Keycloak, Auth0)
- **Local**: Login com credenciais locais
- **JWT**: Tokens de acesso (15 min) + Refresh (7 dias)

### Sistema RBAC

**Roles:**
- `ADMIN`: Acesso total ao sistema
- `ANALISTA`: Aprovar/pendenciar/cancelar cadastros
- `TESOUREIRO`: Registrar pagamentos, gerar contratos
- `AGENTE`: Criar e editar cadastros
- `ASSOCIADO`: Visualizar próprios cadastros

**Permissões:** 23 permissões granulares para controle fino de acesso

## 📊 Funcionalidades Implementadas

### Módulo Associados

- ✅ **CRUD Completo**: Criar, listar, visualizar, editar associados
- ✅ **Formulário Multi-etapas**: 4 etapas com validação em tempo real
- ✅ **Validações**: CPF, CEP, telefone, email
- ✅ **Auto-complete**: Endereço via ViaCEP API
- ✅ **Formatação**: Campos formatados automaticamente
- ✅ **Responsivo**: Interface adaptável para mobile/tablet/desktop

### Módulo Cadastros

- ✅ **Lista com Filtros**: Por status, data, busca textual
- ✅ **Status Badges**: Indicadores visuais do status do cadastro
- ✅ **Ações Contextuais**: Submeter, editar, remover baseado no status
- ⏳ **Formulário Completo**: Com dependentes e upload de documentos
- ⏳ **Cálculo de Valores**: Automático baseado em regras de negócio

### Infraestrutura

- ✅ **Upload de Arquivos**: Validação, preview, organização
- ✅ **Geração de PDF**: Contratos e comprovantes
- ✅ **SSE**: Eventos em tempo real
- ✅ **Cache**: Redis para performance
- ✅ **Jobs Assíncronos**: Celery para processamento pesado

## 🎯 Próximos Passos

### Semana 1-2: Completar Módulo Cadastros
- [ ] Formulário de cadastro com dependentes
- [ ] Upload e validação de documentos
- [ ] Cálculo automático de valores
- [ ] Páginas de detalhe e edição
- [ ] Integração SSE para updates em tempo real

### Semana 3-4: Módulo Análise
- [ ] Dashboard de análise com cadastros pendentes
- [ ] Interface de revisão de documentos
- [ ] Ações de aprovação/pendência/cancelamento
- [ ] Histórico de análises
- [ ] Notificações em tempo real

### Semana 5-6: Módulo Tesouraria
- [ ] Dashboard de tesouraria
- [ ] Pipeline de 6 etapas (pagamento → assinatura → conclusão)
- [ ] Formulário de registro de pagamentos
- [ ] Upload de comprovantes
- [ ] Geração e preview de contratos
- [ ] Integração com NuVideo (assinatura digital)

### Semana 7-8: Relatórios e Finalização
- [ ] Dashboard de relatórios com KPIs
- [ ] Gráficos e visualizações (Recharts)
- [ ] Exportação CSV/Excel
- [ ] Testes E2E para fluxos críticos
- [ ] Polimento de UI/UX
- [ ] Documentação completa

## 🧪 Testes

```bash
# Backend
cd apps/api
python manage.py test

# Frontend
cd apps/web
pnpm test

# E2E (quando implementado)
pnpm test:e2e
```

## 📚 Documentação

- [PRD](./docs/PRD.md) - Product Requirements Document
- [Arquitetura](./docs/ARCHITECTURE.md) - Documentação técnica
- [Fase 2](./docs/FASE_2_CONCLUIDA.md) - Detalhes da Fase 2
- [API Docs](http://localhost:8000/api/docs) - Documentação da API (dev)

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 👥 Equipe

- **Desenvolvimento**: Claude Code + Equipe ABASE
- **Arquitetura**: Django + Next.js + TypeScript
- **Design**: HeroUI + Tailwind CSS

## 📞 Suporte

Para suporte e dúvidas:
- Abra uma [issue](https://github.com/ghitflux/abasev2/issues)
- Consulte a [documentação](./docs/)
- Verifique os [troubleshooting](./docs/TROUBLESHOOTING.md)

---

**Última atualização**: Janeiro 2025  
**Versão**: 2.0.0-beta  
**Status**: Desenvolvimento Ativo