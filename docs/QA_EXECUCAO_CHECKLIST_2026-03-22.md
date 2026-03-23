# Execução QA do Checklist Web

Atualizado em 2026-03-22.

Status geral: em andamento.

## Escopo desta rodada

Esta execução iniciou pela `Fase 0` do checklist em [CHECKLIST_WEB_E2E_POR_FLUXO.md](/mnt/d/apps/abasev2/abasev2/docs/CHECKLIST_WEB_E2E_POR_FLUXO.md), com navegação automatizada em Chromium headless rodando dentro do container `frontend`.

Objetivo desta primeira bateria:

- validar redirects sem sessão
- validar login por papel
- validar redirects de bloqueio para rotas indevidas
- confirmar visibilidade do item `Dashboard` no menu de perfil

## Correção aplicada durante a execução

Foi encontrado e corrigido um bug real no web:

- arquivo: [proxy.ts](/mnt/d/apps/abasev2/abasev2/apps/web/src/proxy.ts)
- problema: rota protegida sem sessão redirecionava para `/login` e descartava o parâmetro `next`
- correção: o redirect agora preserva `next` com a rota originalmente solicitada

Após a correção, o `frontend` foi reiniciado e a fase 0 foi retestada.

## Fase 0 Retestada

### Guards sem sessão

- `/` -> `OK`
  resultado: redireciona para `http://localhost:3000/login`
- `/dashboard` sem sessão -> `OK`
  resultado: `http://localhost:3000/login?next=%2Fdashboard`

### Login e redirect por papel

- `AGENTE` -> `OK`
  resultado: `http://localhost:3000/agentes/meus-contratos`
- `ANALISTA` -> `OK`
  resultado: `http://localhost:3000/analise`

### Bloqueio por papel incorreto

- `AGENTE` abrindo `/dashboard` -> `OK`
  resultado: redirecionado para `http://localhost:3000/agentes/meus-contratos`
- `ANALISTA` abrindo `/tesouraria/despesas` -> `OK`
  resultado: redirecionado para `http://localhost:3000/analise`

### Menu de perfil

- `AGENTE` sem item `Dashboard` -> `OK`
- `ANALISTA` sem item `Dashboard` -> `OK`
- `COORDENADOR` com item `Dashboard` -> pendente de reteste nesta rodada
- `ADMIN` com item `Dashboard` -> pendente de reteste nesta rodada

## Observações da execução

- O primeiro smoke runner amplo gerou falso negativo em alguns redirects por timing de navegação e foi substituído por um reteste mais objetivo da fase 0.
- A automação de navegador não pôde rodar no host local por falta de bibliotecas do Chromium; a execução foi movida para dentro do container `frontend`.
- O checklist completo ainda não foi finalizado nesta rodada. Próximas fases previstas:
  - `Fase 1`: agente
  - `Fase 2`: associados compartilhados
  - `Fase 3`: analista
  - `Fase 4`: coordenação
  - `Fase 5`: tesouraria
  - `Fase 6`: admin

## Evidência técnica usada

- credenciais de desenvolvimento em [SETUP_LOCAL.md](/mnt/d/apps/abasev2/abasev2/docs/SETUP_LOCAL.md)
- runner de smoke em [checklist_phase0_smoke.mjs](/mnt/d/apps/abasev2/abasev2/scripts/qa/checklist_phase0_smoke.mjs)
