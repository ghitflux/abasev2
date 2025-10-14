# ABASE v2 — Bloco 2 e Fase 2

## Regras Absolutas
- Nunca usar SQLite.
- Usar Redis para cache/sessões/blacklist.
- JWT de 15 min + Refresh 7 dias; httpOnly cookies no BFF.
- Strategy + Factory + Singleton em Auth.

## Endpoints (principais)
- POST /api/v1/auth/oidc/callback
- POST /api/v1/auth/refresh
- POST /api/v1/auth/logout
- GET  /api/v1/auth/me
- POST /api/v1/cadastros/associados
- POST /api/v1/cadastros/cadastros {associado_id}
- POST /api/v1/cadastros/cadastros/{id}/submit
- POST /api/v1/analise/cadastros/{id}/aprovar|pendenciar|cancelar
- POST /api/v1/tesouraria/cadastros/{id}/(receber|comprovantes|nuvideo|gerar-contrato|assinar|concluir)
- GET  /api/v1/sse/stream (SSE canal global)

## SSE
- Backend publica Redis channel `events:all`; frontend consome via EventSource.

## Event Sourcing Light
- Tabela `EventLog(entity_type, entity_id, event_type, payload, actor_id, created_at)`.

## Erros
- Exception handlers em `api/exception_handlers.py`.

## Jobs
- `infrastructure/jobs/imports.py:import_associados_csv(path)` com Celery.

## Segurança
- Lockout pós N tentativas (usar cache keys `failed_attempts:`) — extensível.

## Padrões
- Strategy: `core/auth/strategies.py`
- Factory: criação de tokens (na estratégia) e serviços de domínio centralizados
- Singleton: `AuthenticationManager`
