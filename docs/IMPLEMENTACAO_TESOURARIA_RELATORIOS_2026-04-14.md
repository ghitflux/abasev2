# Implementação Tesouraria e Relatórios

Data: 2026-04-14

## Escopo

Esta entrega alterou o fluxo operacional da tesouraria para contratos novos e renovações, alinhou permissões de leitura da coordenação nas rotas da tesouraria e expandiu a infraestrutura de relatórios para permitir definição pública e seleção de colunas por exportação.

## Tesouraria de Contratos

- O comprovante do associado passou a ser o gatilho da efetivação.
- O comprovante do agente passou a ser opcional e pode ser anexado ou substituído depois.
- O endpoint `POST /api/v1/tesouraria/contratos/{id}/efetivar/` continua existindo por compatibilidade, mas agora exige apenas `comprovante_associado`.
- O endpoint `POST /api/v1/tesouraria/contratos/{id}/substituir-comprovante/` passou a funcionar como `upsert`.
- Quando o comprovante do associado é enviado em contrato ainda pendente na tesouraria, o backend:
  - cria ou substitui o comprovante ativo do associado
  - registra `data_anexo_associado`
  - registra `data_pagamento_associado`
  - cria ou atualiza o `Pagamento` inicial
  - efetiva o contrato
- Quando o comprovante do agente é enviado, o backend cria ou substitui o comprovante ativo do agente e sincroniza o pagamento inicial se ele já existir.

## Tesouraria de Renovações

- O comprovante do associado passou a efetivar a renovação automaticamente.
- O comprovante do agente continua opcional e substituível antes ou depois da efetivação.
- Foi adicionado `POST /api/v1/tesouraria/refinanciamentos/{id}/substituir-comprovante/`.
- O endpoint `POST /api/v1/tesouraria/refinanciamentos/{id}/efetivar/` passou a aceitar `comprovante_agente` como opcional.
- O backend agora faz `upsert` dos comprovantes de renovação e sincroniza os campos do pagamento correspondente.

## Campos Achatados e Filtros Backend

Listagens de contratos da tesouraria e de refinanciamentos agora expõem:

- `data_anexo_associado`
- `data_anexo_agente`
- `data_pagamento_associado`
- `data_pagamento_agente`

As listagens backend também aceitam filtros por intervalo para esses campos.

Nas filas de análise e coordenação, o filtro `pagamento_feito` passou a ser suportado com base em `data_pagamento_associado`.

## Relatórios

- Foi adicionado `GET /api/v1/relatorios/definicao/`.
- `POST /api/v1/relatorios/exportar/` agora aceita `filtros.columns`.
- O serviço de relatórios respeita a seleção de colunas em PDF, XLSX, CSV e JSON.
- Foram cadastradas definições para:
  - `/tesouraria`
  - `/tesouraria/refinanciamentos`
  - `/analise/aptos`
  - `/coordenacao/refinanciamento`
  - `/coordenacao/refinanciados`
  - tipos legados do módulo administrativo de relatórios

## Frontend

- `/tesouraria`
  - upload do associado agora usa `substituir-comprovante` imediatamente
  - upload do agente também usa `substituir-comprovante`
  - ações mutáveis ficam restritas a `ADMIN` e `TESOUREIRO`
  - novas colunas de datas de anexo e pagamento foram adicionadas na tabela
- `/tesouraria/refinanciamentos`
  - fluxo de upload imediato adotado para associado e agente
  - remoção do bloqueio visual que exigia os dois comprovantes para efetivar
  - coordenação fica em modo leitura
  - novas colunas de datas de anexo e pagamento foram adicionadas
- `/analise/aptos`
  - exportação passou a aceitar `pagamento_feito`
- `/coordenacao/refinanciamento`
  - exportação passou a aceitar `pagamento_feito`
- `/coordenacao/refinanciados`
  - exportação estruturada substituiu `window.print()`
- `/relatorios`
  - exportações PDF e XLSX agora usam o mesmo diálogo com seleção de colunas

## Permissões

- A tesouraria de refinanciamentos passou a permitir leitura para `COORDENADOR` nas ações seguras.
- Ações mutáveis dessas rotas continuam restritas a `TESOUREIRO` e `ADMIN`.
- No frontend, botões operacionais de escrita foram bloqueados para coordenação nas páginas alteradas.

## Validação Executada

- `python -m py_compile` executado com sucesso nos arquivos backend alterados.
- `git diff --check` executado com sucesso.

## Pendências Conhecidas

- Os filtros backend por `data_anexo_*` e `data_pagamento_*` estão implementados, mas a UI dos filtros avançados de `/tesouraria` e `/tesouraria/refinanciamentos` ainda não expõe todos esses intervalos como campos dedicados.
- A suíte Django não foi executada neste ambiente porque a criação do banco de teste falhou com erro de autenticação MySQL.
