# CLAUDE.md — ABASE v2 Backend

> Contexto operacional para Claude Code na instância backend do monorepo ABASE v2.

## Identidade do Projeto

Backend do ABASE v2 — sistema de gestão de associados para a ABASE Piauí. API REST com Django 6 + DRF, servindo frontend Next.js 16. Banco MySQL 8 (utf8mb4). Tarefas assíncronas via Celery + Redis. O módulo mais crítico é o processamento do Arquivo Retorno (importação mensal dos órgãos públicos para baixa de parcelas).

## Stack Técnica

- Python 3.12+ com Django 6.0.2 (patches CVE-2026-1207, CVE-2026-1287, CVE-2026-1312)
- Django REST Framework 3.15+ para API REST
- DRF Spectacular para OpenAPI 3.1 spec (consumido pelo Kubb no frontend)
- djangorestframework-simplejwt para JWT (access 15min, refresh 7dias)
- django-filter para filtros em ViewSets
- django-cors-headers para CORS
- Celery 5 + Redis 7 (broker/backend) — processa Arquivo Retorno
- MySQL 8 (NUNCA SQLite, NUNCA PostgreSQL)
- mysqlclient como driver, Pillow, openpyxl

## Estrutura

```
backend/
├── config/settings/{base,development,production,testing}.py
├── apps/
│   ├── accounts/      # Auth + RBAC (User, Role, permissions)
│   ├── associados/    # Domínio principal (Associado, Endereco, DadosBancarios)
│   ├── contratos/     # Contrato, Ciclo, Parcela
│   ├── esteira/       # EsteiraItem, Transicao, Pendencia (state machine)
│   ├── refinanciamento/  # Refinanciamento, Comprovante
│   ├── tesouraria/    # Confirmacao, Averbacao
│   ├── importacao/    # ← CRUCIAL: ArquivoRetorno, ArquivoRetornoItem, ImportacaoLog
│   └── relatorios/    # PDF/Excel exports
├── core/              # BaseModel, Singleton, pagination, exceptions
└── manage.py
```

## Design Patterns Obrigatórios

### Strategy — apps/*/strategies.py
Toda lógica que varia por role, status ou contexto. Exemplo crucial no módulo importacao:

```python
# apps/importacao/strategies.py
class ParseStrategy(ABC):
    @abstractmethod
    def parse(self, arquivo_path: str) -> list[dict]: ...

class CSVRetornoParser(ParseStrategy):
    """Faz parse de arquivos CSV do retorno de órgãos públicos."""
    def parse(self, arquivo_path):
        # Normaliza CPF, competência, valor; valida formato
        ...

class ExcelRetornoParser(ParseStrategy):
    """Faz parse de arquivos XLSX do retorno."""
    def parse(self, arquivo_path):
        # Usa openpyxl para ler, normaliza mesmos campos
        ...

class ReconciliacaoStrategy(ABC):
    @abstractmethod
    def reconciliar(self, item: ArquivoRetornoItem) -> str: ...
```

### Factory Method — apps/*/factories.py
Criação de objetos complexos (ContratoFactory, CicloFactory, etc.)

### Singleton — core/singleton.py
Recursos compartilhados (configurações, conexões externas).

## Módulo Arquivo Retorno (importacao/) — Detalhamento

Este é o módulo mais crítico e complexo do sistema. Processa o arquivo retorno dos órgãos públicos para fazer a baixa automática de parcelas.

```python
# apps/importacao/services.py
class ArquivoRetornoService:
    """Orquestra todo o fluxo de processamento do arquivo retorno."""
    
    def upload(self, arquivo, orgao_origem, competencia, user):
        """Cria registro e dispara task Celery."""
        
    def processar(self, arquivo_retorno_id):
        """Chamado pela Celery task. Executa parse → reconciliação → pós-processamento."""
        
    def _parse(self, arquivo_retorno):
        """Escolhe ParseStrategy (CSV/Excel) e cria ArquivoRetornoItems."""
        
    def _reconciliar(self, arquivo_retorno):
        """Para cada item: busca Associado por CPF → busca Parcela da competência → aplica baixa."""
        
    def _pos_processamento(self, arquivo_retorno):
        """Detecta ciclos completos (3/3), cria novos ciclos, identifica encerramentos."""
```

```python
# apps/importacao/tasks.py
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def processar_arquivo_retorno(self, arquivo_retorno_id):
    """Task Celery que processa o arquivo retorno de forma assíncrona."""
    service = ArquivoRetornoService()
    try:
        service.processar(arquivo_retorno_id)
    except Exception as exc:
        # Marca como erro, loga, retry
        self.retry(exc=exc)
```

```python
# apps/importacao/reconciliacao.py
class MotorReconciliacao:
    """Cruza dados do arquivo retorno com associados e parcelas do sistema."""
    
    def reconciliar_item(self, item: ArquivoRetornoItem) -> str:
        # 1. Busca Associado por cpf_cnpj
        associado = Associado.objects.filter(cpf_cnpj=normalize_cpf(item.cpf_cnpj)).first()
        if not associado:
            return 'nao_encontrado'
        
        # 2. Busca Parcela em aberto para a competência
        parcela = Parcela.objects.filter(
            ciclo__contrato__associado=associado,
            referencia_mes=item.competencia,
            status='em_aberto'
        ).first()
        
        # 3. Aplica baixa conforme status_desconto
        if item.status_desconto == 'efetivado':
            parcela.status = 'descontado'
            parcela.data_pagamento = timezone.now().date()
            parcela.save()
            return 'baixa_efetuada'
        elif item.status_desconto == 'rejeitado':
            parcela.status = 'nao_descontado'
            parcela.save()
            return 'nao_descontado'
```

## Models Arquivo Retorno

- **ArquivoRetorno**: registro de cada upload (arquivo_nome, formato, orgao_origem, competencia, status, resultado_resumo JSON)
- **ArquivoRetornoItem**: cada linha do arquivo (cpf_cnpj, matricula_servidor, valor_descontado, status_desconto, associado_id FK NULL, parcela_id FK NULL, resultado_processamento)
- **ImportacaoLog**: log de auditoria de cada passo (tipo, mensagem, dados JSON)

## Convenções

- Todo model herda BaseModel (created_at, updated_at, deleted_at)
- Soft delete sempre (nunca DELETE real)
- Matrícula: MAT-{id:05d} (imutável)
- Código contrato: CTR-{timestamp}-{random}
- Separar serializers leitura/escrita
- Lógica de negócio em services.py (nunca na view)
- Filtros via django-filter
- Paginação via core.pagination.StandardResultsSetPagination
- URLs com prefixo /api/v1/ e DefaultRouter

## Regras de Negócio Críticas

1. Matrícula imutável após geração (MAT-XXXXX)
2. Comissão agente = 10% sempre
3. Ciclo = exatamente 3 parcelas mensais consecutivas
4. Refinanciamento requer 3/3 parcelas pagas + 3 mensalidades livres reais
5. Esteira sequencial: cadastro → análise → coordenação → tesouraria → concluído
6. Pendência sempre retorna para o agente
7. Soft delete em tudo
8. Importação do arquivo retorno é idempotente (reimportar não duplica)
9. Analista assume exclusivo (um por vez)
10. Efetivação requer comprovante PIX
11. Arquivo retorno: cruzamento por CPF/CNPJ é case-insensitive e ignora formatação
12. CPF/CNPJ único por associado

## Variáveis de Ambiente

```env
DJANGO_SETTINGS_MODULE=config.settings.development
SECRET_KEY=chave-secreta
DATABASE_URL=mysql://abase:senha@mysql:3306/abase_v2
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CORS_ALLOWED_ORIGINS=http://localhost:3000
JWT_ACCESS_TOKEN_LIFETIME=15
JWT_REFRESH_TOKEN_LIFETIME=10080
```
