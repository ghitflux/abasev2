# ABASE v2 — Plano Completo de Desenvolvimento

> Sistema Web de Gestão de Associados da ABASE Piauí
> Stack: Django 6 · Next.js 16 · MySQL 8 · Tailwind 4 · shadcn/ui · Docker · pnpm Workspaces · Kubb · Jest
> Última atualização: 11 de março de 2026

---

## 1. Visão Geral do Sistema

O ABASE v2 é uma aplicação web completa para gestão de associados de uma associação de servidores públicos do Piauí. O sistema controla todo o ciclo de vida de um associado, desde o cadastro inicial feito por um Agente de campo até a efetivação do contrato pela Tesouraria, passando por múltiplas etapas de validação documental e aprovação hierárquica, e culminando no processamento mensal do arquivo retorno dos órgãos públicos para confirmação de descontos em folha de pagamento.

O sistema opera com cinco papéis distintos (AGENTE, ANALISTA, COORDENADOR, TESOUREIRO e ADMIN), cada um com responsabilidades e telas específicas.

### 1.1. Fluxo Principal de Negócio

```
AGENTE cadastra associado com documentação
    ↓
Associado entra na ESTEIRA DE ANÁLISE
    ↓
ANALISTA assume → Valida documentação
    ├── Pendência → Retorna para AGENTE → Volta para esteira
    └── Aprovado → Encaminha para COORDENAÇÃO
         ↓
COORDENADOR faz segunda validação
    ├── Rejeita → Retorna
    └── Aprova → Encaminha para TESOURARIA
         ↓
TESOUREIRO efetiva contrato + comprovante PIX
    ↓
Associado ATIVO com 1º ciclo (3 parcelas)
    ↓
IMPORTAÇÃO MENSAL DO ARQUIVO RETORNO (crucial)
    ├── Descontado em folha → Baixa automática da parcela
    ├── Não descontado → Marca inadimplente
    └── Última parcela (3/3) → Previsão encerramento
    ↓
Ciclo completo (3/3 pagas) → Elegível para REFINANCIAMENTO → Novo ciclo
```

### 1.2. O Arquivo Retorno — Módulo Crucial

O Arquivo Retorno é o mecanismo central de baixa financeira do sistema. Para a ABASE, o formato real de trabalho é o relatório ETIPI / iNETConsig em `.txt`, com colunas fixas, cabeçalho repetido por página, subtotais por órgão e legenda de status no final. O arquivo de referência atual está em `docs/ABASE (2).txt`.

O fluxo principal desta versão não deve assumir CSV ou Excel como origem principal. CSV/XLSX podem existir no futuro, mas o plano de implementação deve priorizar o layout TXT real fornecido pela operação.

**Estrutura real esperada do arquivo:**

```text
Entidade: 2102-Assoc. Benef. e Assist. dos Serv. Públicos - ABASE             Referência: 05/2025   Data da Geração: 23/05/2025
STATUS MATRICULA NOME                           CARGO                          FIN. ORGAO LANC.  TOTAL PAGO  VALOR        ORGAO PAGTO CPF
  1    030759-9  MARIA DE JESUS SANTANA COSTA   -                              6580      002     999   001          30.00      002    23993596315
```

**Características obrigatórias do parser:**

- arquivo texto com encoding compatível com `ISO-8859-1`;
- linhas de detalhe em largura fixa;
- competência extraída do cabeçalho `Referência: MM/YYYY`;
- quebra de página por form-feed;
- linhas de subtotal por órgão pagador;
- linhas de subtotal por status;
- legenda final com códigos `1,2,3,4,5,6,S`.

**Mapeamento de status do arquivo real para o sistema:**

- `1` → `efetivado` → baixa automática se valor e parcela forem coerentes
- `2` → `rejeitado` → marca não descontado
- `3` → `rejeitado` → marca não descontado
- `4` → `pendente` → revisão manual
- `5` → `pendente` → revisão manual
- `6` → `pendente` → revisão manual
- `S` → `rejeitado` → marca não descontado

**Fluxo de processamento (Celery async):**

```
1. UPLOAD → Cria ArquivoRetorno (status=pendente) → Dispara Celery task
2. PARSE → ETIPITxtRetornoParser normaliza linhas úteis e extrai metadados
3. PERSISTÊNCIA → Cria ArquivoRetornoItem com status bruto e status normalizado
4. RECONCILIAÇÃO → Cruza CPF × Associado × Parcela da competência
   ├── efetivado coerente → parcela.status = descontado
   ├── rejeitado → parcela.status = nao_descontado
   ├── pendente → mantém em aberto e registra revisão manual
   └── não encontrado → log de erro
5. PÓS-PROCESSAMENTO:
   ├── 3/3 pagas → Ciclo renovado → Novo ciclo criado (se elegível)
   ├── Última parcela → Previsão de encerramento
   └── Atualiza resumo com contadores e pendências manuais
6. RESULTADO → Frontend exibe cards, histórico e status de reconciliação
```

---

## 2. Arquitetura do Sistema

### 2.1. Monorepo com pnpm Workspaces

```yaml
# pnpm-workspace.yaml
packages:
  - 'apps/*'
  - 'packages/*'
```

```
abase-v2/
├── pnpm-workspace.yaml
├── package.json                  # Root: scripts globais, devDeps comuns
├── pnpm-lock.yaml                # Lock file único
├── .npmrc                        # strict mode, link-workspace-packages=true
│
├── apps/
│   └── web/                      # @abase/web — Frontend Next.js 16
│       ├── package.json
│       ├── next.config.ts
│       ├── kubb.config.ts
│       ├── components.json       # shadcn/ui (TODOS 50 componentes)
│       └── src/
│
├── packages/
│   ├── tsconfig/                 # @abase/tsconfig
│   ├── eslint-config/            # @abase/eslint-config
│   └── shared-types/             # @abase/shared-types
│
├── backend/                      # Django 6 (Python, não é workspace pnpm)
│   ├── config/
│   ├── apps/
│   │   ├── accounts/
│   │   ├── associados/
│   │   ├── contratos/
│   │   ├── esteira/
│   │   ├── refinanciamento/
│   │   ├── tesouraria/
│   │   ├── importacao/           # ← MÓDULO CRUCIAL: Arquivo Retorno
│   │   └── relatorios/
│   ├── core/
│   └── manage.py
│
├── docker/
├── docker-compose.yml
├── Makefile
└── .env.example
```

### 2.2. Frontend: Componentes Completos

O frontend instala de antemão TODOS os 50 componentes do shadcn/ui, eliminando a necessidade de instalar componentes avulsos durante o desenvolvimento. Além disso, 14 componentes customizados compostos são criados para atender aos requisitos específicos do ABASE:

**Componentes Customizados (src/components/custom/):**

- **DatePicker** — Popover + Calendar com formatação pt-BR (date-fns locale)
- **DateRangePicker** — Seleção de período com dois calendários
- **TimePicker** — Input com máscara HH:MM e validação
- **DateTimePicker** — DatePicker + TimePicker combinados
- **SearchableSelect** — Command + Popover (combobox com busca)
- **MultiSelect** — Command + Badge tags para seleção múltipla
- **InputCurrency** — Input com máscara R$ X.XXX,XX
- **InputCpfCnpj** — Input com máscara dinâmica CPF/CNPJ
- **InputPhone** — Input com máscara (XX) XXXXX-XXXX
- **InputCep** — Input com máscara + auto-complete de endereço via API
- **DropdownActions** — DropdownMenu padronizado para ações de tabela
- **FileUploadDropzone** — Drag-and-drop com validação de tipo, priorizando `.txt` para arquivo retorno ETIPI
- **CalendarCompetencia** — MonthPicker (mês/ano) para competência
- **StatusBadge** — Badge com cores mapeadas por status do sistema

### 2.3. Backend: Módulo de Importação (Arquivo Retorno)

```
backend/apps/importacao/
├── models.py          # ArquivoRetorno, ArquivoRetornoItem, ImportacaoLog
├── serializers.py     # Upload, detalhe, itens filtrados
├── views.py           # Upload endpoint, consultas filtradas
├── services.py        # ArquivoRetornoService (orquestra todo o fluxo)
├── tasks.py           # Celery: processar_arquivo_retorno (async)
├── parsers.py         # ETIPITxtRetornoParser + strategies para formatos futuros
├── validators.py      # Validação de arquivo TXT, cabeçalho, CPF, competência
├── reconciliacao.py   # Motor de cruzamento CPF × Associado × Parcela
└── tests/             # TestCase por parser, validator, service e reconciliacao
```

---

## 3. Modelagem — Tabelas do Arquivo Retorno

### ArquivoRetorno

| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | BIGINT PK | Identificador |
| arquivo_nome | VARCHAR(255) | Nome original do arquivo |
| arquivo_url | TEXT | Caminho armazenado |
| formato | VARCHAR(4) | txt, csv ou xlsx |
| orgao_origem | VARCHAR(100) | Origem lógica detectada do arquivo, ex: ETIPI/iNETConsig |
| competencia | DATE | Mês/ano extraído do cabeçalho do arquivo |
| total_registros | INT | Total de linhas |
| processados | INT | Processados com sucesso |
| nao_encontrados | INT | CPFs não encontrados |
| erros | INT | Erros de formato |
| status | VARCHAR(20) | pendente/processando/concluido/erro |
| resultado_resumo | JSON | {baixa_efetuada, nao_descontado, pendencias_manuais, nao_encontrado, novos_ciclos, encerramentos} |
| uploaded_by_id | FK→User | Quem fez upload |
| processado_em | DATETIME NULL | Quando Celery terminou |

### ArquivoRetornoItem

| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | BIGINT PK | Identificador |
| arquivo_retorno_id | FK | Arquivo pai |
| linha_numero | INT | Número da linha original |
| cpf_cnpj | VARCHAR(18) | CPF/CNPJ do servidor |
| matricula_servidor | VARCHAR(50) | Matrícula no órgão |
| nome_servidor | VARCHAR(255) | Nome como veio no arquivo |
| cargo | VARCHAR(255) | Cargo bruto vindo do relatório |
| competencia | VARCHAR(7) | MM/YYYY |
| valor_descontado | DECIMAL(10,2) | Valor descontado |
| status_codigo | VARCHAR(1) | Código bruto ETIPI: 1,2,3,4,5,6,S |
| status_desconto | VARCHAR(20) | efetivado/rejeitado/cancelado/pendente |
| status_descricao | VARCHAR(255) | Descrição humana do código de status |
| motivo_rejeicao | TEXT NULL | Motivo quando rejeitado |
| orgao_codigo | VARCHAR(10) | Código do órgão na linha |
| orgao_pagto_codigo | VARCHAR(10) | Código do órgão pagador do bloco |
| orgao_pagto_nome | VARCHAR(255) | Nome do órgão pagador extraído do subtotal do bloco |
| associado_id | FK→Associado NULL | Cruzamento encontrado |
| parcela_id | FK→Parcela NULL | Parcela que teve baixa |
| processado | BOOLEAN | Item já processado |
| resultado_processamento | VARCHAR(30) | baixa_efetuada/nao_descontado/nao_encontrado/erro/ciclo_aberto |
| payload_bruto | JSON | Snapshot bruto da linha parseada |

### ImportacaoLog

| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | BIGINT PK | Identificador |
| arquivo_retorno_id | FK | Arquivo retorno |
| tipo | VARCHAR(20) | upload/parse/validacao/reconciliacao/baixa/erro |
| mensagem | TEXT | Descrição do evento |
| dados | JSON NULL | Contexto |

---

## 4. Roadmap de 4 Semanas

### SEMANA 1 — Fundação (Dias 1-7)
- Dias 1-2: Monorepo pnpm + Docker + todos os 50 shadcn components
- Dias 3-4: Todos os models (incluindo ArquivoRetorno) + migrations
- Dias 5-6: Auth JWT + RBAC + 14 componentes customizados
- Dia 7: Layout base (Sidebar, Header, shared components)

### SEMANA 2 — CRUD + Esteira (Dias 8-14)
- Dias 8-9: CRUD Associados (backend)
- Dias 10-11: CRUD Associados (frontend com componentes customizados)
- Dias 12-13: Esteira de Análise completa
- Dia 14: Contratos do Agente

### SEMANA 3 — Tesouraria + Refinanciamento (Dias 15-21)
- Dias 15-16: Tesouraria (dashboard, efetivação PIX)
- Dias 17-18: Confirmações (Ligação & Averbação com CalendarCompetencia)
- Dias 19-20: Refinanciamento + Coordenação
- Dia 21: Refinanciamentos do Tesoureiro

### SEMANA 4 — Arquivo Retorno + Polish (Dias 22-28)
- Dias 22-23: **Arquivo Retorno Backend** com parser ETIPI TXT, reconciliação, Celery task e testes
- Dia 24: **Arquivo Retorno Frontend** com upload `.txt`, polling, cards de resultado e histórico
- Dia 25: Renovação de Ciclos
- Dia 26: Kubb + OpenAPI integration
- Dia 27: Testes + Segurança
- Dia 28: Documentação + roteiro de QA manual
