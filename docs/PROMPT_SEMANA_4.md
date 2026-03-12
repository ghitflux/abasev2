# PROMPT SEMANA 4 — Arquivo Retorno ETIPI + Renovação de Ciclos + Kubb + Testes + Segurança

> Prompt para Claude Code executar a Semana 4 do ABASE v2.
> Pré-requisito: Semana 3 completa.
> Este prompt substitui a premissa antiga de CSV/XLSX como fluxo principal do arquivo retorno.
> Arquivo de referência obrigatório: `docs/ABASE (2).txt`.

## Escopo da Semana

A Semana 4 deve entregar:

1. processamento do arquivo retorno real fornecido pela ABASE, no formato ETIPI/iNETConsig em `.txt`;
2. tela de importação e acompanhamento do processamento;
3. dashboard de renovação de ciclos;
4. integração OpenAPI + Kubb para os endpoints criados nesta semana;
5. testes automatizados com `django.test.TestCase` no backend e `Jest` no frontend;
6. ajustes de segurança para upload, permissões e reconciliação;
7. documentação de QA manual para backend e frontend.

## Fora de Escopo Nesta Semana

- não executar deploy;
- não criar `docker-compose.prod.yml`;
- não criar NGINX de produção;
- não configurar CI/CD agora;
- não usar Vitest no frontend.

Ao final desta semana o sistema deve ficar pronto para validação manual de QA, não para publicação em produção.

---

## Premissas Obrigatórias

1. O arquivo real em `docs/ABASE (2).txt` manda mais do que qualquer hipótese anterior do prompt.
2. O fluxo principal do arquivo retorno desta semana é `.txt` em layout fixo ETIPI/iNETConsig, não CSV.
3. O arquivo de exemplo é texto `ISO-8859` com `CRLF`, cabeçalhos repetidos por página e quebra de página por form-feed.
4. A competência deve ser extraída do cabeçalho `Referência: MM/YYYY`, não escolhida manualmente no frontend.
5. O arquivo contém múltiplos órgãos pagadores no mesmo upload; portanto, `orgao_origem` não deve depender de seleção manual por órgão individual.
6. Se o modelo atual não comportar os dados do arquivo real, ajuste models e migrations.
7. O backend deve seguir o padrão já existente do projeto: `django.test.TestCase`, `override_settings`, fixtures e testes por app.
8. O frontend deve ser configurado com `Jest` + `Testing Library` + `next/jest`.
9. Kubb deve cobrir os endpoints da Semana 4 sem reintroduzir chamadas manuais onde houver hook gerado.

---

## Contexto do Arquivo Retorno Real

O arquivo real fornecido pela ABASE tem estas características:

- origem: ETIPI / iNETConsig;
- extensão real de trabalho desta semana: `.txt`;
- encoding esperado: `ISO-8859-1` ou compatível;
- linhas de detalhe em colunas fixas;
- cabeçalho repetido em todas as páginas;
- linhas de subtotal por órgão pagador;
- linhas de subtotal por status;
- legenda final de status;
- competência e data de geração no cabeçalho da página.

Exemplo de cabeçalho real:

```text
Entidade: 2102-Assoc. Benef. e Assist. dos Serv. Públicos - ABASE             Referência: 05/2025   Data da Geração: 23/05/2025
STATUS MATRICULA NOME                           CARGO                          FIN. ORGAO LANC.  TOTAL PAGO  VALOR        ORGAO PAGTO CPF
```

Legenda real do status:

```text
1 - Lançado e Efetivado
2 - Não Lançado por Falta de Margem Temporariamente
3 - Não Lançado por Outros Motivos
4 - Lançado com Valor Diferente
5 - Não Lançado por Problemas Técnicos
6 - Lançamento com Erros
S - Não Lançado: Compra de Dívida ou Suspensão SEAD
```

Mapeamento obrigatório para a camada de negócio:

| Código | Descrição ETIPI | Status normalizado | Baixa automática |
|--------|------------------|--------------------|------------------|
| `1` | Lançado e Efetivado | `efetivado` | Sim |
| `2` | Falta de margem | `rejeitado` | Não |
| `3` | Outros motivos | `rejeitado` | Não |
| `4` | Valor diferente | `pendente` | Não |
| `5` | Problemas técnicos | `pendente` | Não |
| `6` | Lançamento com erros | `pendente` | Não |
| `S` | Compra de dívida / suspensão | `rejeitado` | Não |

Regra importante:

- `status_codigo` bruto deve ser persistido;
- `status_desconto` normalizado deve continuar existindo para a regra de reconciliação;
- `motivo_rejeicao` ou `observacao` deve guardar a descrição humana do código.

---

## BLOCO 13 — Arquivo Retorno Backend (Dia 22-23)

### Tarefa 13.1: Ajustar models e migrations para o arquivo real

Revisar `backend/apps/importacao/models.py` e criar migration complementar.

Mudanças mínimas esperadas:

1. adicionar `TXT` em `ArquivoRetorno.Formato`;
2. permitir que o upload desta semana use `formato="txt"`;
3. enriquecer `ArquivoRetornoItem` com dados brutos do arquivo real.

Campos recomendados em `ArquivoRetornoItem`:

```python
class ArquivoRetornoItem(BaseModel):
    status_codigo = models.CharField(max_length=1, blank=True)
    status_descricao = models.CharField(max_length=255, blank=True)
    cargo = models.CharField(max_length=255, blank=True)
    orgao_codigo = models.CharField(max_length=10, blank=True)
    orgao_pagto_codigo = models.CharField(max_length=10, blank=True)
    orgao_pagto_nome = models.CharField(max_length=255, blank=True)
    payload_bruto = models.JSONField(default=dict, blank=True)
```

Se preferir não expandir o schema com todos esses campos, no mínimo persistir:

- `status_codigo`;
- `status_descricao`;
- `orgao_codigo`;
- `orgao_pagto_codigo`;
- `orgao_pagto_nome`;
- `payload_bruto`.

Também ajustar `ArquivoRetorno.formato` para:

```python
class Formato(models.TextChoices):
    TXT = "txt", "TXT"
    CSV = "csv", "CSV"
    XLSX = "xlsx", "XLSX"
```

### Tarefa 13.2: Criar parser específico ETIPI/iNETConsig

Criar em `backend/apps/importacao/parsers.py` um parser orientado ao layout real do arquivo.

Manter Strategy Pattern, mas com esta prioridade:

1. `ETIPITxtRetornoParser` como parser obrigatório desta semana;
2. estrutura preparada para CSV/XLSX no futuro, sem tratá-los como fluxo principal agora.

Estrutura sugerida:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


class ParseStrategy(ABC):
    @abstractmethod
    def parse(self, arquivo_path: str) -> list[dict]:
        ...


@dataclass
class RetornoMeta:
    competencia: str
    data_geracao: str
    entidade: str
    sistema_origem: str = "ETIPI/iNETConsig"


class ETIPITxtRetornoParser(ParseStrategy):
    STATUS_MAP = {
        "1": ("efetivado", "Lançado e Efetivado"),
        "2": ("rejeitado", "Não Lançado por Falta de Margem Temporariamente"),
        "3": ("rejeitado", "Não Lançado por Outros Motivos"),
        "4": ("pendente", "Lançado com Valor Diferente"),
        "5": ("pendente", "Não Lançado por Problemas Técnicos"),
        "6": ("pendente", "Lançamento com Erros"),
        "S": ("rejeitado", "Não Lançado: Compra de Dívida ou Suspensão SEAD"),
    }

    def parse(self, arquivo_path: str) -> list[dict]:
        ...
```

Regras obrigatórias do parser:

1. abrir o arquivo com fallback de encoding priorizando `latin-1`;
2. normalizar `\r\n` e remover `\x0c`;
3. ignorar cabeçalhos de página repetidos;
4. ignorar linha de separação `====== ======== ...`;
5. ignorar `Total do Status:`;
6. ignorar a seção `Legenda do Status`;
7. extrair `competencia` e `data_geracao` do cabeçalho `Referência: MM/YYYY`;
8. identificar linhas de detalhe reais;
9. processar o arquivo em blocos para conseguir anexar `orgao_pagto_nome` vindo da linha `Órgão Pagamento: ...`;
10. gerar itens normalizados prontos para persistência.

### Tarefa 13.2.1: Estratégia de parsing por blocos

Não usar `csv.DictReader`.

Usar parsing por blocos:

1. acumular linhas de detalhe consecutivas;
2. ao encontrar a linha `Órgão Pagamento:`, preencher `orgao_pagto_nome` e, se necessário, `orgao_pagto_codigo` nos itens acumulados daquele bloco;
3. ao encontrar `Total do Status:` ou mudança de página, flush do buffer;
4. linhas de status `3` que não trazem resumo de órgão não devem quebrar o parser; nesses casos, `orgao_pagto_nome` pode ficar vazio.

### Tarefa 13.2.2: Campos normalizados por item

Cada item parseado deve produzir algo equivalente a:

```python
{
    "linha_numero": int,
    "cpf_cnpj": "23993596315",
    "matricula_servidor": "030759-9",
    "nome_servidor": "MARIA DE JESUS SANTANA COSTA",
    "cargo": "-",
    "competencia": "05/2025",
    "valor_descontado": Decimal("30.00"),
    "status_codigo": "1",
    "status_desconto": "efetivado",
    "status_descricao": "Lançado e Efetivado",
    "motivo_rejeicao": None,
    "orgao_codigo": "002",
    "orgao_pagto_codigo": "002",
    "orgao_pagto_nome": "SEC. EST. ADMIN. E PREVIDEN.",
    "payload_bruto": {...},
}
```

### Tarefa 13.2.3: Regras de normalização

- CPF: somente dígitos;
- nome: `strip()` e upper preservado;
- cargo: `strip()`, aceitar `-` e vazio;
- valor: `Decimal`, lendo `30.00` com ponto decimal;
- competência: manter `MM/YYYY` no item e converter para `date` no `ArquivoRetorno`;
- `orgao_origem` do arquivo: usar `ETIPI/iNETConsig` ou nome equivalente derivado do cabeçalho, não pedir um órgão individual do usuário.

### Tarefa 13.3: Validadores específicos para TXT de retorno

Criar em `backend/apps/importacao/validators.py`:

```python
class ArquivoRetornoValidator:
    @staticmethod
    def validar_formato(arquivo_nome):
        ...

    @staticmethod
    def validar_tamanho(arquivo, max_mb=20):
        ...

    @staticmethod
    def validar_cabecalho(lines):
        ...

    @staticmethod
    def validar_item(item):
        ...
```

Validações obrigatórias:

1. extensão permitida nesta semana: `.txt`;
2. arquivo não vazio;
3. presença de `Entidade:` e `Referência:`;
4. presença da linha de colunas `STATUS MATRICULA NOME ... CPF`;
5. `status_codigo` dentro de `1,2,3,4,5,6,S`;
6. CPF com 11 dígitos;
7. competência válida;
8. valor numérico não negativo;
9. parser não deve explodir se houver linha malformada: registrar log e seguir quando possível.

### Tarefa 13.4: Motor de reconciliação com regras reais

Criar ou refatorar `backend/apps/importacao/reconciliacao.py`.

Regras obrigatórias:

1. buscar associado preferencialmente por CPF normalizado;
2. buscar parcela em aberto para a competência;
3. usar `select_for_update()` e idempotência;
4. processar `status_codigo` junto com `status_desconto`.

Regras de negócio:

- `1` / `efetivado`:
  - só dar baixa automática se a parcela existir e o valor for coerente;
  - preencher `data_pagamento`;
  - se houver divergência de valor, não baixar automaticamente; registrar como revisão manual.

- `2`, `3` e `S`:
  - marcar parcela como `nao_descontado`;
  - atualizar inadimplência quando aplicável;
  - registrar motivo detalhado na observação.

- `4`, `5` e `6`:
  - não baixar automaticamente;
  - manter a parcela em aberto;
  - registrar em `ImportacaoLog` e `observacao` como inconsistência para revisão manual.

- CPF não encontrado:
  - `resultado_processamento = nao_encontrado`.

- reprocessamento:
  - não duplicar baixa;
  - não abrir ciclo duplicado.

### Tarefa 13.5: Serviço, task e endpoints

Criar ou completar:

- `backend/apps/importacao/services.py`
- `backend/apps/importacao/tasks.py`
- `backend/apps/importacao/serializers.py`
- `backend/apps/importacao/views.py`

Fluxo esperado:

1. upload do arquivo `.txt`;
2. validação inicial;
3. criação de `ArquivoRetorno` com `status=pendente`;
4. disparo da task Celery;
5. parse e persistência dos itens;
6. reconciliação;
7. atualização de resumo;
8. endpoints para consulta do resultado.

Mudanças importantes em relação ao prompt antigo:

- remover dependência de seleção manual de órgão no upload;
- competência deve vir do arquivo;
- o resumo precisa contemplar `pendencias_manuais` além de `baixa_efetuada`, `nao_descontado`, `nao_encontrado`, `erro`, `ciclo_aberto`, `encerramento`.

Endpoints mínimos desta semana:

- `POST /api/v1/importacao/arquivo-retorno/upload/`
- `GET /api/v1/importacao/arquivo-retorno/`
- `GET /api/v1/importacao/arquivo-retorno/{id}/`
- `GET /api/v1/importacao/arquivo-retorno/{id}/descontados/`
- `GET /api/v1/importacao/arquivo-retorno/{id}/nao-descontados/`
- `GET /api/v1/importacao/arquivo-retorno/{id}/pendencias-manuais/`
- `GET /api/v1/importacao/arquivo-retorno/{id}/encerramentos/`
- `GET /api/v1/importacao/arquivo-retorno/{id}/novos-ciclos/`
- `GET /api/v1/importacao/arquivo-retorno/ultima/`
- `POST /api/v1/importacao/arquivo-retorno/{id}/reprocessar/`

### Tarefa 13.6: Testes backend com Django TestCase

Criar testes em:

- `backend/apps/importacao/tests/test_parsers.py`
- `backend/apps/importacao/tests/test_validators.py`
- `backend/apps/importacao/tests/test_reconciliacao.py`
- `backend/apps/importacao/tests/test_services.py`

Usar `django.test.TestCase`, `override_settings`, fixtures locais e, se necessário, `SimpleUploadedFile`.

Criar fixture de referência baseada em `docs/ABASE (2).txt`, por exemplo:

- `backend/apps/importacao/tests/fixtures/retorno_etipi_052025.txt`

Cobertura mínima de cenários:

1. lê arquivo `latin-1` corretamente;
2. ignora cabeçalhos repetidos, subtotais, legenda e form-feed;
3. extrai competência e data de geração do cabeçalho;
4. normaliza status `1,2,3,4,5,6,S`;
5. preenche `orgao_pagto_nome` a partir da linha de resumo do bloco;
6. funciona mesmo quando o bloco não tem linha `Órgão Pagamento`;
7. baixa automática com status `1`;
8. `2`, `3` e `S` geram `nao_descontado`;
9. `4`, `5` e `6` vão para revisão manual;
10. idempotência de reprocessamento;
11. ciclo completo cria novo ciclo sem duplicidade;
12. CPF não encontrado;
13. divergência de valor não baixa automaticamente.

Comando de execução esperado:

```bash
docker compose exec backend python manage.py test apps.importacao -v 2
```

Não usar `pytest` nesta semana.

---

## BLOCO 14 — Arquivo Retorno Frontend (Dia 24)

### Tarefa 14.1: Tela de importação aderente ao arquivo real

Criar ou refatorar `apps/web/src/app/(dashboard)/importacao/page.tsx`.

Mudanças obrigatórias em relação ao prompt antigo:

1. aceitar upload de `.txt`, não de CSV/XLSX como fluxo principal;
2. remover campo manual de `Órgão de Origem`;
3. remover seleção manual de competência;
4. exibir mensagem de que a competência será extraída do arquivo;
5. usar os hooks gerados pelo Kubb para upload, polling e listagem.

### Seção 1 — Upload

Usar `FileUploadDropzone` adaptado para:

- aceitar `.txt`;
- exibir texto como `Importar Relatório de Retorno`;
- informar `Formato esperado: relatório ETIPI/iNETConsig`;
- mostrar limite de tamanho;
- iniciar upload multipart;
- enquanto status estiver `processando`, fazer polling a cada 3 segundos.

Feedback esperado:

- `Arquivo enviado com sucesso`;
- `Competência detectada: 05/2025`;
- `Sistema origem: ETIPI/iNETConsig`;
- `Processando arquivo retorno...`.

### Seção 2 — Resultado da última importação

Manter os 3 cards principais do design:

1. `Associados Descontados`
2. `Previsão de Encerramento`
3. `Novos Ciclos Abertos`

Adicionar um resumo compacto acima ou ao lado com os status do arquivo real:

- efetivados;
- não descontados;
- pendências manuais;
- não encontrados;
- erros.

Cada linha de detalhe deve exibir, quando fizer sentido:

- nome;
- matrícula;
- CPF mascarado;
- órgão pagador;
- valor;
- status bruto ETIPI;
- status normalizado do sistema.

### Seção 3 — Histórico de importações

Tabela sugerida:

| Coluna | Conteúdo |
|--------|----------|
| Data/Hora | upload ou processamento |
| Arquivo | nome do `.txt` |
| Sistema Origem | ETIPI/iNETConsig |
| Referência | competência extraída |
| Total | linhas úteis |
| Processados | total reconciliado |
| Não Encontrados | contador |
| Erros | contador |
| Status | badge |

### Tarefa 14.2: Ajustar componentes de upload

Se necessário, adaptar:

- `FileUploadDropzone`
- `StatusBadge`
- cards de resumo
- tabela de histórico

para refletir:

- `.txt` como tipo aceito;
- nova taxonomia de resultado;
- casos de pendência manual.

---

## BLOCO 15 — Renovação de Ciclos (Dia 25)

### Tarefa 15.1: Backend de renovação

Manter o objetivo funcional do plano completo, com endpoints para:

- visão mensal;
- lista de meses;
- detalhamento de associados;
- exportação.

Reforçar a dependência com a importação:

- os dados mensais devem refletir o resultado da reconciliação do arquivo retorno;
- `encerramentos` e `novos ciclos` precisam bater com o resumo da importação;
- a criação automática de ciclo deve aparecer no dashboard administrativo.

### Tarefa 15.2: Frontend de renovação

Criar ou refatorar:

- `apps/web/src/app/(dashboard)/renovacao-ciclos/page.tsx`

Usar hooks gerados pelo Kubb e refletir estes estados:

- ciclo renovado;
- apto a renovar;
- em aberto;
- ciclo iniciado;
- inadimplente / não descontado quando aplicável.

---

## BLOCO 16 — OpenAPI + Kubb (Dia 26)

### Tarefa 16.1: Regenerar schema OpenAPI

Usar o fluxo atual do repositório:

```bash
pnpm generate:schema
```

ou, equivalentemente:

```bash
docker compose run --rm backend python manage.py spectacular --file /app/schema.yaml --validate
```

Garantir que a spec inclua os endpoints novos de:

- importação;
- reprocessamento;
- pendências manuais;
- renovação de ciclos.

### Tarefa 16.2: Regenerar clients com Kubb

Usar:

```bash
pnpm generate:api
```

ou:

```bash
pnpm --filter @abase/web generate:api
```

Esperado:

- hooks gerados para upload, listagem, detalhe, polling e renovação;
- `apps/web/src/gen` atualizado;
- sem reintroduzir fetch manual para os endpoints da Semana 4.

### Tarefa 16.3: Substituir chamadas manuais

Para tudo que for novo nesta semana:

- usar hooks do Kubb;
- manter React Query coerente com o projeto;
- invalidar queries após upload e reprocessamento.

---

## BLOCO 17 — Testes + Segurança + Preparação para QA Manual (Dia 27-28)

### Tarefa 17.1: Testes backend

Executar com Django test runner:

```bash
docker compose exec backend python manage.py test apps.importacao apps.tesouraria apps.contratos -v 2
```

Não usar `pytest` nesta semana.

Prioridades:

- parser do arquivo ETIPI;
- reconciliação;
- idempotência;
- abertura de novos ciclos;
- atualização de inadimplência;
- regras de divergência de valor;
- permissões dos endpoints.

### Tarefa 17.2: Testes frontend com Jest

Configurar Jest no frontend.

Dependências esperadas:

```bash
pnpm --filter @abase/web add -D jest @types/jest jest-environment-jsdom next/jest @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

Arquivos esperados:

- `apps/web/jest.config.ts` ou `apps/web/jest.config.js`
- `apps/web/jest.setup.ts`
- script `test` em `apps/web/package.json`

Estratégia:

- usar `next/jest`;
- `testEnvironment: "jest-environment-jsdom"`;
- `setupFilesAfterEnv` com `@testing-library/jest-dom`.

Casos mínimos:

1. `FileUploadDropzone` aceita `.txt` e rejeita formatos inválidos;
2. tela de importação entra em polling após upload;
3. cards de resultado renderizam contadores corretamente;
4. histórico de importações renderiza status e referência;
5. componentes que dependem de hooks do Kubb devem mockar os hooks, não usar fetch manual.

Comando esperado:

```bash
pnpm --filter @abase/web test
```

Não usar Vitest.

### Tarefa 17.3: Segurança

Aplicar e validar:

1. permissões do upload apenas para perfis autorizados;
2. validação estrita de extensão e tamanho do arquivo;
3. sanitização de nome do arquivo salvo;
4. parser resiliente a linhas malformadas;
5. logs de erro auditáveis;
6. proteção contra reprocessamento concorrente;
7. CORS coerente com o ambiente atual;
8. rate limiting para upload e login, se já estiver dentro do escopo do backend.

### Tarefa 17.4: Preparação para QA manual

Não executar deploy.

Em vez disso, gerar um roteiro de QA manual, por exemplo:

- `docs/QA_SEMANA_4.md`

Esse roteiro deve conter cenários para backend e frontend:

1. upload de arquivo válido;
2. upload de arquivo inválido;
3. status `1` com baixa automática;
4. status `2` ou `3` gerando não descontado;
5. status `4` gerando pendência manual;
6. CPF não encontrado;
7. reprocessamento;
8. criação automática de ciclo;
9. atualização dos cards do frontend;
10. histórico de importações;
11. permissões de acesso;
12. smoke test dos hooks gerados pelo Kubb.

Entregável desta etapa:

- sistema pronto para sua rodada manual de QA;
- sem etapa de deploy executada.

---

## Checklist Final da Semana 4

- [ ] `ArquivoRetorno.Formato` suporta `txt`
- [ ] migration complementar criada para o formato real
- [ ] parser `ETIPITxtRetornoParser` implementado
- [ ] leitura `latin-1` / `ISO-8859-1` funcionando
- [ ] parser ignora cabeçalhos, subtotais, legenda e form-feed
- [ ] competência extraída do cabeçalho `Referência: MM/YYYY`
- [ ] `status_codigo` bruto persistido por item
- [ ] mapeamento de status `1,2,3,4,5,6,S` implementado
- [ ] `orgao_pagto_nome` e metadados do bloco extraídos quando disponíveis
- [ ] regras de reconciliação revisadas para `efetivado`, `rejeitado` e `pendente`
- [ ] divergência de valor não gera baixa automática
- [ ] idempotência de reprocessamento garantida
- [ ] novos ciclos abertos sem duplicidade
- [ ] upload frontend aceita `.txt`
- [ ] competência não é escolhida manualmente no frontend
- [ ] histórico de importações mostra referência, status e contadores
- [ ] OpenAPI inclui os endpoints da Semana 4
- [ ] Kubb gera hooks para importação e renovação
- [ ] backend testado com `python manage.py test`
- [ ] frontend testado com `Jest`
- [ ] nenhum trecho novo usa Vitest
- [ ] nenhum item de deploy foi executado nesta semana
- [ ] roteiro de QA manual entregue em documentação

---

## Resumo Executivo para o Agente

Refatore a Semana 4 para o mundo real da ABASE:

- o arquivo retorno é um `.txt` ETIPI/iNETConsig em layout fixo;
- a competência vem do cabeçalho do arquivo;
- o upload não é por órgão individual;
- o backend deve persistir status bruto e status normalizado;
- reconciliação só baixa automaticamente quando a regra de negócio permitir;
- frontend usa Kubb e aceita `.txt`;
- testes frontend são com Jest;
- deploy fica fora do escopo;
- a saída final deve incluir preparação para QA manual.
