# Correção de Parcelas de Março/2026 — Sessão 2026-04-06

## Objetivo

Restaurar o banco local com os dados de produção, baixar o arquivo retorno de março/2026 do servidor e aplicar em massa a correção de status nas parcelas de março sem reconstruir ciclos.

---

## Contexto anterior (sessão 2026-04-05)

Na sessão anterior foram corrigidos:

- Login do admin (`ALLOWED_HOSTS` não incluía `backend` e `localhost`)
- EncodeError no Celery (task retornava objeto Django não serializável)
- Erro 500 em `confirmar` e `cancelar` quando `ArquivoRetorno.DoesNotExist`
- OOM kills nos workers Gunicorn durante processamento do arquivo retorno:
  - `@transaction.atomic` quebrado em duas fases (lock curto só para mudança de status)
  - Loop de `rebuild_contract_cycle_state` convertido para chunks de 50 com `gc.collect()`
  - Workers Gunicorn reduzidos de 4 para 2
  - Limites de memória Docker: backend `2g`, celery `1g`

O banco de produção estava com **3.104 associados fantasma** com `status=IMPORTADO`, criados automaticamente pela função `upsert_imported_associado_from_retorno` quando o arquivo retorno registrava CPFs não encontrados na base real.

---

## 1. Deploy dos commits pendentes

### Situação

| Local (HEAD) | VPS |
|---|---|
| `17b9d93` | `092fd0c` |

Havia 4 commits pendentes:

```
17b9d93  docs: atualizar ROTINAS_POR_PERFIL_E_ROTAS com visão funcional completa
b7977e6  Stabilize import polling and duplicate summaries
da1a0f6  Tune production memory distribution and runtime
5a0981b  Harden return import polling and Celery fallback
```

### Ações

```bash
# Push para o remote que o VPS usa
git push abasenewv2 abaseprod

# No VPS
cd /opt/ABASE/repo
git pull origin abaseprod

# Rebuild sem cache: backend, celery e frontend
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  build --no-cache backend celery frontend

# Restart com force-recreate
docker compose -f deploy/hostinger/docker-compose.prod.yml \
  --env-file /opt/ABASE/env/.env.production \
  up -d --force-recreate backend celery frontend
```

### Resultado

```
abase-frontend-prod   Up (healthy)
abase-backend-prod    Up (healthy)   — agora usa gthread workers
abase-celery-prod     Up (healthy)
abase-nginx-prod      Up (healthy)
abase-redis-prod      Up (healthy)
abase-mysql-prod      Up (healthy)
```

> Mudança relevante dos commits novos: o backend passou a usar `gthread` workers no Gunicorn em vez de `sync`, melhorando concorrência e reduzindo risco de OOM.

---

## 2. Sincronização do banco local com produção

### Problema

O banco local estava desatualizado. O dump anterior (feito na sessão anterior) não continha os registros do import de março/2026 feito hoje.

### Script criado: `scripts/sync_db_from_prod.py`

Faz todo o processo via paramiko (SSH/SFTP), sem precisar de acesso manual ao servidor.

**Fluxo do script:**

1. Conecta via SSH em `deploy@abasepiaui.com` usando `~/.ssh/abase_deploy`
2. Cria diretório de backup em `/opt/ABASE/data/backups`
3. Executa `mysqldump` dentro do container `abase-mysql-prod`
4. Verifica tamanho do dump (falha se menor que 1 KB)
5. Baixa via SFTP para `backups/dump_prod_TIMESTAMP.sql`
6. Remove o dump do servidor
7. Garante que o MySQL local (`abase-v2-mysql-1`) está rodando
8. Recria o banco `abase` (DROP + CREATE utf8mb4)
9. Copia o dump para dentro do container e importa
10. Exibe verificação de associados por status

**Uso:**

```bash
python scripts/sync_db_from_prod.py
```

**Configurações internas do script:**

```python
SSH_HOST         = "abasepiaui.com"
SSH_USER         = "deploy"
SSH_KEY          = "~/.ssh/abase_deploy"

PROD_CONTAINER   = "abase-mysql-prod"
PROD_DB_NAME     = "abase_v2"
PROD_DB_USER     = "abase"

LOCAL_CONTAINER  = "abase-v2-mysql-1"
LOCAL_DB_NAME    = "abase"
LOCAL_DB_PASSWORD = "abase"   # MYSQL_ROOT_PASSWORD=${DATABASE_PASSWORD:-abase}
```

> **Atenção:** A senha do root local é `abase` mesmo com `DATABASE_PASSWORD=` vazio no `.env`, porque o docker-compose usa `:-abase` como fallback: `MYSQL_ROOT_PASSWORD: ${DATABASE_PASSWORD:-abase}`.

**Resultado:**

```
Download concluido: 17.3 MB local
Importacao concluida.

Verificacao associados:
status          total
inadimplente    393
ativo           202
em_analise       84
inativo           6
cadastrado        2
```

Total: **687 associados reais** — sem os 3.104 fantasmas de produção.

---

## 3. Download do arquivo retorno de março/2026

### Identificação do arquivo

```sql
SELECT id, competencia, status, arquivo_nome, arquivo_url, total_registros, processados, created_at
FROM importacao_arquivoretorno
WHERE DATE(created_at) = CURDATE();
```

```
id=46  competencia=2026-03-01  status=concluido
arquivo_nome=Relatorio_D2102-03-2026.txt
arquivo_url=arquivos_retorno/f77380907be34652919cbcc719cd4619_Relatorio_D2102-03-2026.txt
total_registros=661  processados=661  created_at=2026-04-06 12:09:10
```

### Download via paramiko

```python
import paramiko
from pathlib import Path

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("abasepiaui.com", username="deploy",
               key_filename=str(Path.home() / ".ssh" / "abase_deploy"),
               look_for_keys=False, allow_agent=False)

sftp = client.open_sftp()
sftp.get(
    "/opt/ABASE/data/media/arquivos_retorno/f77380907be34652919cbcc719cd4619_Relatorio_D2102-03-2026.txt",
    "backups/Relatorio_D2102-03-2026.txt"
)
sftp.close()
client.close()
```

Arquivo salvo em `backups/Relatorio_D2102-03-2026.txt` (111.8 KB).

### Formato do arquivo (ETIPI/iNETConsig)

```
Entidade: 2102-Assoc. Benef. e Assist. dos Serv. Públicos - ABASE
Referência: 03/2026   Data da Geração: 24/03/2026

STATUS MATRICULA NOME                           CARGO         FIN. ORGAO ... CPF
====== ========= ============================== ============= ============ ... ===========
  1    007638-4  MARIA DO SOCORRO RUBEN PEREIRA ...           ...          ... 20168942372
  2    076503-1  VALDIRENE PINHEIRO DIAS AVENDA  ...
  3    385626-7  PEDRO MOURA ALMONDES            ...
```

**Legenda de status:**

| Código | Significado |
|--------|-------------|
| 1 | Lançado e Efetivado |
| 2 | Não Lançado por Falta de Margem Temporariamente |
| 3 | Não Lançado por Outros Motivos |
| 4 | Lançado com Valor Diferente |
| 5 | Não Lançado por Problemas Técnicos |
| 6 | Lançamento com Erros |
| S | Não Lançado: Compra de Dívida ou Suspensão SEAD |

**Distribuição no arquivo de março:**

| Status | Qtd |
|--------|-----|
| 1 (efetivado) | 182 |
| 2 (sem margem) | 450 |
| 3 (outros motivos) | 29 |
| **Total** | **661** |

---

## 4. Correção em massa das parcelas de março/2026

### Motivação

O banco local foi restaurado de produção **antes** do import de março/2026 ter sido feito (dump às 10:37, import às 12:09). Por isso as parcelas de março ainda estavam em `em_aberto` ou `em_previsao`. Precisavam refletir o que o arquivo retorno reportou.

Os ciclos **não** foram rebuildados para evitar o problema de OOM que afetou a sessão anterior.

### Script: `backend/corrigir_parcelas_marco.py`

Rodado via `docker exec` no container `abase-v2-backend-1` (que monta `./backend:/app`).

**Fluxo:**

1. Setup do Django (`config.settings.development`)
2. Parse do arquivo com `ETIPITxtRetornoParser` (parser existente do projeto)
3. Indexa 661 CPFs do arquivo por `cpf_cnpj` → `status_codigo`
4. Carrega todas as parcelas `referencia_mes=2026-03-01` não canceladas/liquidadas do banco
5. Indexa parcelas por `CPF do associado`
6. Para cada CPF do arquivo:
   - `status_codigo = "1"` → `Parcela.DESCONTADO` + `data_pagamento = 2026-03-24`
   - `status_codigo 2/3/4/5/6/S` → `Parcela.NAO_DESCONTADO` + `observacao` com descrição do motivo
7. Executa `bulk update` dentro de `transaction.atomic()`
8. Exibe resumo e CPFs sem correspondência

**Como rodar:**

```bash
# Copiar arquivo retorno para dentro do backend (que é montado no container)
cp backups/Relatorio_D2102-03-2026.txt backend/backups/

# Executar no container local
echo "s" | docker exec -i abase-v2-backend-1 bash -c "cd //app && python corrigir_parcelas_marco.py"
```

> No Git Bash no Windows, prefixar caminhos com `//` evita a conversão automática de `/app` para `C:/Program Files/Git/app`.

### Descobertas durante a execução

| Problema | Causa | Solução |
|----------|-------|---------|
| `AttributeError: 'ParsedRetorno' object has no attribute 'rows'` | Campo correto é `items` | `result.rows` → `result.items` |
| `AttributeError: 'ParsedRetorno' object has no attribute 'competencia'` | Metadados ficam em `result.meta` | `result.competencia` → `result.meta.competencia` |
| 0 CPFs extraídos | Campo correto é `cpf_cnpj`, não `cpf` | `row.get("cpf")` → `row.get("cpf_cnpj")` |
| Status incorreto | Campo correto é `status_codigo`, não `status_code` | `row.get("status_code")` → `row.get("status_codigo")` |

### Resultado final

| Resultado | Parcelas |
|-----------|----------|
| DESCONTADO aplicado | **121** |
| NAO_DESCONTADO aplicado | **323** |
| Sem registro no arquivo retorno | 6 |
| CPFs no arquivo sem parcela no banco local | 217 |

```
Resumo pós-atualização: {'nao_descontado': 323, 'descontado': 121}
Ciclos NÃO rebuildados.
```

> Os 217 CPFs presentes no arquivo sem parcela local correspondem a servidores da ETIPI/iNETConsig que **não são associados da ABASE** — situação normal do arquivo retorno que é gerado para toda a folha do estado, não apenas para os associados da ABASE.

---

## Estrutura dos campos do `ParsedRetorno` (referência)

```python
# result.meta
result.meta.competencia      # "03/2026"
result.meta.data_geracao     # "24/03/2026"

# result.items — cada item é um dict com:
{
    "linha_numero":       int,
    "cpf_cnpj":           str,   # apenas dígitos, 11 chars
    "matricula_servidor": str,
    "nome_servidor":      str,
    "cargo":              str,
    "competencia":        str,   # "03/2026"
    "valor_descontado":   Decimal,
    "status_codigo":      str,   # "1", "2", "3", "S", ...
    "status_desconto":    str,   # "efetivado" / "rejeitado" / "pendente"
    "status_descricao":   str,   # texto longo
    "motivo_rejeicao":    str | None,
    "orgao_codigo":       str,
    "orgao_pagto_codigo": str,
    "orgao_pagto_nome":   str,
    "payload_bruto":      dict,
}
```

---

## Arquivos produzidos

| Arquivo | Propósito |
|---------|-----------|
| `scripts/sync_db_from_prod.py` | Sincroniza banco local com produção via paramiko |
| `backend/corrigir_parcelas_marco.py` | Aplica correção em massa nas parcelas de março |
| `backups/Relatorio_D2102-03-2026.txt` | Arquivo retorno de março/2026 (baixado da produção) |
| `backups/dump_prod_20260406_103758.sql` | Dump do banco de produção de 06/04/2026 10:37 |

---

## Pendências conhecidas

1. **3.104 associados fantasma em produção** — criados pela função `upsert_imported_associado_from_retorno` que cria novos `Associado` com `status=IMPORTADO` quando o CPF não é encontrado. Precisam ser removidos em produção com script equivalente ao de correção local.

2. **6 parcelas de março sem CPF no arquivo** — requerem investigação manual para determinar se estão corretas ou precisam de ajuste.

3. **Arquivo retorno de outubro/2025 a fevereiro/2026** — ainda precisam ser aplicados conforme orientação do usuário (aplicará os demais após validar março).
