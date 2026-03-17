# PROMPT SEMANA 2 — CRUD Associados + Esteira de Análise + Contratos

> Prompt para Claude Code executar a Semana 2 do ABASE v2.
> Pré-requisito: Semana 1 completa (monorepo pnpm, Docker, models, auth JWT, layout base, 50 shadcn + 14 custom components).

## Contexto da Semana

A Semana 2 implementa o core funcional do sistema: o CRUD completo de associados (backend e frontend), a esteira de análise onde o analista valida documentação, e a tela "Meus Contratos" do agente. Ao final desta semana o fluxo Agente → Analista estará funcional end-to-end.

---

## BLOCO 5 — CRUD Associados Backend (Dia 8-9)

### Tarefa 5.1: Serializers de Associados

Criar em `apps/associados/serializers.py` dois conjuntos de serializers — leitura e escrita, conforme convenção do CLAUDE.md:

**AssociadoListSerializer (leitura — tabela):** campos para a tela de listagem conforme o mockup da Image 2. Deve retornar: `id`, `nome_completo`, `matricula`, `cpf_cnpj`, `status`, `agente` (nested: id + full_name), `ciclos_abertos` (annotated count), `ciclos_fechados` (annotated count). O campo `ciclos_abertos` e `ciclos_fechados` são calculados via annotation no queryset, não são campos do model.

**AssociadoDetailSerializer (leitura — detalhe):** retorna o associado completo com todos os relacionamentos nested: `endereco` (EnderecoSerializer), `dados_bancarios` (DadosBancariosSerializer), `contato` (ContatoHistoricoSerializer), `contratos` (ContratoResumoSerializer, many=True), `documentos` (DocumentoSerializer, many=True), `esteira` (EsteiraItemResumoSerializer, nullable). Cada sub-serializer é de leitura com todos os campos do respectivo model.

**AssociadoCreateSerializer (escrita — cadastro):** aceita dados flat e nested para criação atômica. O formulário do agente (conforme PDF Capture 001) envia tudo de uma vez. Campos obrigatórios do associado: `tipo_documento`, `cpf_cnpj`, `nome_completo`. Campos opcionais: `rg`, `orgao_expedidor`, `data_nascimento`, `profissao`, `estado_civil`. Nested objects que devem ser criados junto: `endereco` (cep, endereco, numero, complemento, bairro, cidade, uf), `dados_bancarios` (banco, agencia, conta, tipo_conta, chave_pix), `contato` (celular, email, orgao_publico, situacao_servidor, matricula_servidor). Além disso, dados do contrato: `valor_bruto_total`, `valor_liquido`, `prazo_meses`, `taxa_antecipacao`, `mensalidade`, `margem_disponivel`. O `validate()` deve verificar unicidade de cpf_cnpj, calcular automaticamente a comissão do agente (10%), gerar a matrícula (MAT-XXXXX) e o código do contrato (CTR-timestamp-random). O `create()` deve, em uma transaction.atomic(): criar Associado, Endereco, DadosBancarios, ContatoHistorico, Contrato (com valores calculados), Ciclo (primeiro, com 3 referências mensais a partir do mês seguinte), 3 Parcelas (status=em_aberto), e EsteiraItem (etapa=cadastro, status=aguardando).

**AssociadoUpdateSerializer (escrita — edição):** permite atualização parcial. Nested objects são atualizados via update, não recriados. Matrícula e cpf_cnpj não podem ser alterados (read_only no update).

**AssociadoMetricasSerializer (leitura — cards):** retorna `total`, `ativos`, `em_analise`, `inativos`, cada um com `count` e `variacao_percentual` (comparação com mês anterior). Este serializer é alimentado por um método do service, não por uma queryset direta.

### Tarefa 5.2: Filters

Criar em `apps/associados/filters.py`:

```python
# apps/associados/filters.py
import django_filters
from apps.associados.models import Associado

class AssociadoFilter(django_filters.FilterSet):
    """
    Filtros avançados para listagem de associados.
    Corresponde ao Sheet "Filtros Avançados" no frontend.
    """
    nome = django_filters.CharFilter(
        field_name='nome_completo', lookup_expr='icontains',
        help_text='Busca parcial por nome'
    )
    cpf_cnpj = django_filters.CharFilter(
        field_name='cpf_cnpj', lookup_expr='icontains',
        help_text='Busca parcial por CPF/CNPJ'
    )
    matricula = django_filters.CharFilter(
        field_name='matricula', lookup_expr='icontains'
    )
    status = django_filters.ChoiceFilter(
        choices=Associado.STATUS_CHOICES,
        help_text='Filtrar por status: ativo, inativo, em_analise, inadimplente'
    )
    agente = django_filters.NumberFilter(
        field_name='agente_id',
        help_text='Filtrar por ID do agente responsável'
    )
    orgao_publico = django_filters.CharFilter(
        field_name='contato__orgao_publico', lookup_expr='icontains',
        help_text='Filtrar por órgão público'
    )
    data_cadastro_inicio = django_filters.DateFilter(
        field_name='created_at', lookup_expr='gte'
    )
    data_cadastro_fim = django_filters.DateFilter(
        field_name='created_at', lookup_expr='lte'
    )

    class Meta:
        model = Associado
        fields = ['nome', 'cpf_cnpj', 'matricula', 'status', 'agente',
                  'orgao_publico', 'data_cadastro_inicio', 'data_cadastro_fim']
```

### Tarefa 5.3: Service Layer (Strategy + Factory)

Criar em `apps/associados/services.py`:

```python
# apps/associados/services.py
class AssociadoService:
    """
    Camada de serviço para lógica de negócio de associados.
    Usa Strategy para validações e Factory para criação.
    """

    @staticmethod
    def calcular_metricas():
        """
        Calcula as 4 métricas exibidas nos StatsCards:
        - Total de Associados (com variação % vs mês anterior)
        - Associados Ativos (idem)
        - Em Análise (com diferença absoluta)
        - Inativos (com diferença absoluta)
        """
        # Implementar contagem atual e comparação com mês anterior
        # Retornar dict com count + variacao para cada métrica

    @staticmethod
    def criar_associado_completo(validated_data, agente):
        """
        Cria associado com todos os relacionamentos em uma transação atômica.
        Usa AssociadoFactory para a criação.
        Gera matrícula, código do contrato, ciclo e parcelas.
        Cria EsteiraItem para entrar na esteira de análise.
        """

    @staticmethod
    def buscar_com_contagens(queryset):
        """
        Annotate queryset com contagens de ciclos abertos/fechados
        para exibição na tabela de listagem.
        """
        return queryset.annotate(
            ciclos_abertos=Count('contratos__ciclos',
                filter=Q(contratos__ciclos__status__in=['futuro', 'aberto'])),
            ciclos_fechados=Count('contratos__ciclos',
                filter=Q(contratos__ciclos__status__in=['ciclo_renovado', 'fechado']))
        )
```

Criar em `apps/associados/factories.py`:

```python
# apps/associados/factories.py — Factory Method
class AssociadoFactory:
    """Factory para criação de diferentes tipos de associado."""

    @staticmethod
    def criar_pessoa_fisica(dados, agente):
        """Cria associado PF com matrícula gerada."""
        associado = Associado.objects.create(
            tipo_documento='CPF',
            agente=agente,
            status='em_analise',
            **dados
        )
        # Gera matrícula: MAT-{id:05d}
        associado.matricula = f'MAT-{associado.id:05d}'
        associado.save(update_fields=['matricula'])
        return associado

    @staticmethod
    def criar_pessoa_juridica(dados, agente):
        """Cria associado PJ."""
        # Similar mas com tipo_documento='CNPJ'
```

Criar em `apps/associados/strategies.py`:

```python
# apps/associados/strategies.py — Strategy Pattern
class ValidationStrategy(ABC):
    """Strategy para validação de dados do associado conforme contexto."""
    @abstractmethod
    def validate(self, data: dict) -> dict: ...

class CadastroValidationStrategy(ValidationStrategy):
    """Validação no momento do cadastro (campos mínimos)."""
    def validate(self, data):
        # CPF/CNPJ obrigatório e único, nome obrigatório
        # Calcula margem: valor_liquido * 0.30
        # Calcula comissão: mensalidade * 0.10

class EdicaoValidationStrategy(ValidationStrategy):
    """Validação no momento da edição (matrícula e cpf imutáveis)."""
    def validate(self, data):
        # Impede alteração de matrícula e cpf_cnpj
```

### Tarefa 5.4: ViewSet

Criar em `apps/associados/views.py`:

```python
# apps/associados/views.py
class AssociadoViewSet(ModelViewSet):
    """
    ViewSet para CRUD de associados.
    - GET / → Lista com filtros, paginação e contagens (annotated)
    - POST / → Cadastro completo (nested create)
    - GET /{id}/ → Detalhe com todos os relacionamentos
    - PATCH /{id}/ → Atualização parcial
    - DELETE /{id}/ → Soft delete
    - GET /metricas/ → Cards de métricas (endpoint extra)
    - GET /{id}/ciclos/ → Ciclos do associado
    - POST /{id}/documentos/ → Upload de documento
    """
    filterset_class = AssociadoFilter
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return AssociadoListSerializer
        if self.action == 'retrieve':
            return AssociadoDetailSerializer
        if self.action == 'create':
            return AssociadoCreateSerializer
        return AssociadoUpdateSerializer

    def get_queryset(self):
        qs = Associado.objects.select_related('agente', 'endereco', 'dados_bancarios', 'contato')
        if self.action == 'list':
            qs = AssociadoService.buscar_com_contagens(qs)
        # Agente vê apenas seus associados; Admin vê todos
        if self.request.user.has_role('AGENTE') and not self.request.user.has_role('ADMIN'):
            qs = qs.filter(agente=self.request.user)
        return qs

    def get_permissions(self):
        if self.action in ['create']:
            return [IsAuthenticated(), (IsAgente | IsAdmin)()]
        if self.action in ['destroy']:
            return [IsAuthenticated(), IsAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        # Delega para o Service que usa Factory + Strategy
        AssociadoService.criar_associado_completo(
            serializer.validated_data, self.request.user
        )

    def perform_destroy(self, instance):
        instance.soft_delete()  # Nunca hard delete

    @action(detail=False, methods=['get'])
    def metricas(self, request):
        """Retorna os 4 StatsCards da tela de Associados."""
        data = AssociadoService.calcular_metricas()
        return Response(AssociadoMetricasSerializer(data).data)

    @action(detail=True, methods=['get'])
    def ciclos(self, request, pk=None):
        """Retorna ciclos do associado com parcelas."""
        associado = self.get_object()
        ciclos = Ciclo.objects.filter(
            contrato__associado=associado
        ).prefetch_related('parcelas').order_by('-numero')
        serializer = CicloDetailSerializer(ciclos, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser])
    def documentos(self, request, pk=None):
        """Upload de documento do associado."""
        associado = self.get_object()
        serializer = DocumentoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(associado=associado)
        return Response(serializer.data, status=201)
```

### Tarefa 5.5: URLs

Registrar no router DRF em `config/urls.py`:

```python
router = DefaultRouter()
router.register(r'associados', AssociadoViewSet, basename='associado')
```

**Validação Bloco 5**: Todos os endpoints respondem corretamente via Swagger UI. POST /api/v1/associados/ cria associado + endereco + banco + contato + contrato + ciclo + 3 parcelas + esteira_item em uma transação. GET /api/v1/associados/ retorna lista com contagens de ciclos. GET /api/v1/associados/metricas/ retorna os 4 cards. Filtros funcionam (nome, status, agente, etc.).

---

## BLOCO 6 — CRUD Associados Frontend (Dia 10-11)

### Tarefa 6.1: Tela de Listagem de Associados

Criar `src/app/(dashboard)/associados/page.tsx` reproduzindo fielmente o layout da Image 2:

**Seção 1 — Métricas (4 StatsCards em grid):**
Usar o componente `StatsCard` da Semana 1. Quatro cards lado a lado:
- "Total de Associados" com valor grande (2.845), variação verde (+12.5%) com ícone de seta para cima
- "Associados Ativos" (2.710), variação verde (+8.2%)
- "Em Análise" (85), variação vermelha (-12) com seta para baixo
- "Inativos" (50), variação vermelha (-5)

Hook: `useGetAssociadosMetricas()` gerado pelo Kubb. Se ainda não gerado, criar hook manual que chama GET /api/v1/associados/metricas/.

**Seção 2 — Barra de ações:**
- Input de busca à esquerda ("Buscar associados...") com ícone Search do Lucide. Usa `useDebounce(300ms)` antes de enviar ao backend.
- À direita: botão "Filtros Avançados" (ícone FilterLines, variante outline) que abre Sheet lateral. Botão "+ Novo Associado" (variante primary, laranja) que navega para `/associados/novo`.

**Seção 3 — Tabela de associados:**
Usar o componente `DataTable` da Semana 1 com as seguintes colunas conforme Image 2:

| Coluna | Campo | Renderização |
|--------|-------|--------------|
| Nome | nome_completo | Texto + seta de expand (Collapsible) |
| Matrícula | matricula | Texto monospace (ex: MAT-10042) |
| CPF/CNPJ | cpf_cnpj | Formatado com InputCpfCnpj.format() |
| Ciclos | ciclos_abertos + ciclos_fechados | Duas Badges lado a lado: verde "X abertos", cinza "Y fechados" |
| Agente | agente.full_name | Texto |
| Status | status | Componente StatusBadge |
| Ações | — | Dois ícones: Eye (visualizar → /associados/{id}), Edit (editar → /associados/{id}/editar) |

**Seção 4 — Row expandida (Collapsible):**
Quando o usuário clica na seta de expand de uma row, exibe os ciclos do associado. Para o ciclo futuro, mostra 3 cards de parcela lado a lado (conforme bottom da Image 2): "Parcela 1/3 — Abr/2026 — Em Aberto", "Parcela 2/3 — Mai/2026 — Em Aberto", "Parcela 3/3 — Jun/2026 — Em Aberto". Status "Futuro" exibido no canto direito. Usar Tabs se houver múltiplos ciclos (ativo + futuro).

Hook para dados da tabela: `useGetAssociados({ page, page_size, ordering, ...filters })`. Paginação server-side.

### Tarefa 6.2: Formulário de Cadastro (Multi-Step)

Criar `src/app/(dashboard)/associados/novo/page.tsx` com formulário multi-step reproduzindo todos os campos do PDF Capture 001:

O formulário usa `react-hook-form` + `zodResolver` com schema Zod de validação. Dividido em 5 etapas (steps) com barra de progresso no topo:

**Step 1 — Dados Cadastrais:**
- Tipo de Documento: Select com opções CPF / CNPJ (componente `Select` do shadcn)
- CPF/CNPJ: componente `InputCpfCnpj` (máscara dinâmica conforme tipo selecionado)
- RG: Input text
- Órgão Expedidor: Input text
- Nome Completo / Razão Social: Input text (obrigatório)
- Data de Nascimento: componente `DatePicker` (com calendar pt-BR)
- Profissão: Input text
- Estado Civil: Select (Solteiro, Casado, Divorciado, Viúvo, União Estável)

**Step 2 — Endereço:**
- CEP: componente `InputCep` (máscara + auto-complete ViaCEP que preenche os campos abaixo)
- Endereço: Input text (auto-preenchido pelo CEP)
- Nº: Input text
- Complemento: Input text
- Bairro: Input text (auto-preenchido)
- Cidade: Input text (auto-preenchido)
- UF: Select com 27 estados (auto-preenchido)

**Step 3 — Dados Bancários:**
- Banco: componente `SearchableSelect` com lista de bancos (ex: Banco do Brasil, Caixa, Bradesco, Itaú, etc.)
- Agência: Input text
- Conta: Input text
- Tipo de Conta: Select (Corrente, Poupança, Salário)
- Chave PIX: Input text (CPF/CNPJ, e-mail, celular ou chave aleatória)

**Step 4 — Contato e Vínculo Público:**
- Celular: componente `InputPhone`
- E-mail: Input email
- Órgão Público: componente `SearchableSelect` (Secretaria de Fazenda, Secretaria de Saúde, Secretaria de Educação, Secretaria de Segurança, SSP, etc.)
- Situação do Servidor: Select (Ativo, Afastado, Aposentado, etc.)
- Matrícula do Servidor Público: Input text

**Step 5 — Dados do Contrato:**
- Valor Bruto Total: componente `InputCurrency`
- Valor Líquido (contra-cheque): componente `InputCurrency`
- Prazo de Antecipação (meses): Input number
- 35% do Bruto: campo calculado automaticamente (read-only, valor_bruto * 0.35)
- Margem Líquido - 30% dedução: campo calculado (read-only)
- Mensalidade: componente `InputCurrency`
- Taxa de Antecipação %: Input number com suffix "%"
- Disponível R$: campo calculado (read-only)
- Valor Total Antecipação R$: campo calculado (read-only)
- Data de Aprovação: componente `DatePicker`
- Data da primeira mensalidade: componente `DatePicker`
- Status: Select (Pendente — padrão)
- Mês de Averbação: componente `CalendarCompetencia` (MonthPicker)
- Doação do Associado R$: componente `InputCurrency`

**Seção de Comprovantes (dentro do Step 5):**
7 campos de upload usando `FileUploadDropzone` em grid 3x3:
- Documento (frente)
- Documento (verso)
- Comprovante de residência
- Divulgação
- Contracheque atual
- Termo de Adesão
- Termo de Antecipação

**Botões do formulário:**
- Cada step tem "Voltar" e "Próximo"
- Último step tem "Voltar" e "Enviar Cadastro" (primary, laranja)
- Ao submeter, chama POST /api/v1/associados/ com todos os dados
- Exibe toast de sucesso (Sonner) e redireciona para /associados

**Validação Zod:**
Criar schema com refinements: CPF/CNPJ válido (dígitos verificadores), email válido, CEP com 8 dígitos, valor bruto > 0, mensalidade > 0, data de nascimento no passado.

### Tarefa 6.3: Tela de Detalhe e Edição

**Detalhe** (`src/app/(dashboard)/associados/[id]/page.tsx`):
Página com todas as informações do associado em seções colapsáveis (Accordion): Dados Pessoais, Endereço, Dados Bancários, Contato e Vínculo, Contrato, Ciclos/Parcelas, Documentos, Histórico da Esteira. Cada seção mostra os dados formatados (CPF mascarado, valores em R$, datas em pt-BR). Botão "Editar" no topo.

**Edição** (`src/app/(dashboard)/associados/[id]/editar/page.tsx`):
Mesmo formulário multi-step, mas pré-preenchido com dados atuais. Matrícula e CPF/CNPJ aparecem como disabled. Usa PATCH /api/v1/associados/{id}/.

**Validação Bloco 6**: Tela de listagem carrega com métricas e tabela paginada. Busca filtra em tempo real (debounce). Formulário de cadastro multi-step funciona end-to-end: preencher todos os campos → submeter → associado criado com contrato + ciclo + parcelas + esteira. Row expandida mostra ciclos e parcelas. Detalhe e edição funcionam.

---

## BLOCO 7 — Esteira de Análise (Dia 12-13)

### Tarefa 7.1: EsteiraService (State Machine)

Criar em `apps/esteira/services.py` o serviço que implementa a máquina de estados da esteira:

```python
# apps/esteira/services.py
class EsteiraService:
    """
    State machine para o workflow de aprovação.
    Gerencia transições de etapas e status da esteira.
    
    Transições válidas:
    cadastro(aguardando) → analise(aguardando)         [automático ao criar]
    analise(aguardando)  → analise(em_andamento)        [assumir]
    analise(em_andamento)→ coordenacao(aguardando)      [aprovar]
    analise(em_andamento)→ cadastro(pendenciado)        [pendenciar]
    coordenacao(aguardando)→coordenacao(em_andamento)   [assumir coord]
    coordenacao(em_andamento)→tesouraria(aguardando)    [aprovar]
    coordenacao(em_andamento)→analise(pendenciado)      [rejeitar]
    tesouraria(aguardando)→concluido(aprovado)          [efetivar]
    """

    TRANSICOES_VALIDAS = {
        ('analise', 'aguardando'): ['assumir'],
        ('analise', 'em_andamento'): ['aprovar', 'pendenciar', 'solicitar_correcao'],
        ('coordenacao', 'aguardando'): ['assumir'],
        ('coordenacao', 'em_andamento'): ['aprovar', 'rejeitar'],
        ('tesouraria', 'aguardando'): ['efetivar'],
    }

    @staticmethod
    def assumir(esteira_item, user):
        """Analista ou Coordenador assume o item da esteira."""
        # Valida que ninguém mais assumiu
        # Atualiza analista_id ou coordenador_id
        # Muda status para em_andamento
        # Cria registro de Transicao

    @staticmethod
    def aprovar(esteira_item, user, observacao=''):
        """Aprova e move para próxima etapa."""
        # Valida transição válida
        # Se analise → move para coordenacao
        # Se coordenacao → move para tesouraria
        # Cria Transicao

    @staticmethod
    def pendenciar(esteira_item, user, tipo_pendencia, descricao):
        """Devolve para o agente com pendência."""
        # Cria Pendencia com tipo e descrição
        # Move para cadastro com status pendenciado
        # Cria Transicao

    @staticmethod
    def solicitar_correcao(esteira_item, user, observacao):
        """Solicita correção de documentação ao agente."""
        # Similar a pendenciar mas específico para docs

    @staticmethod
    def validar_documento_revisto(esteira_item, user):
        """Marca documento como validado após reenvio."""
        # Atualiza status dos documentos
        # Permite que o fluxo continue
```

### Tarefa 7.2: ApprovalStrategy

Criar em `apps/esteira/strategies.py`:

```python
# apps/esteira/strategies.py — Strategy por role
class ApprovalStrategy(ABC):
    @abstractmethod
    def can_approve(self, user, esteira_item) -> bool: ...
    @abstractmethod
    def get_next_etapa(self) -> str: ...

class AnalistaApprovalStrategy(ApprovalStrategy):
    def can_approve(self, user, esteira_item):
        return (esteira_item.etapa_atual == 'analise'
                and esteira_item.analista_id == user.id
                and esteira_item.status == 'em_andamento')
    def get_next_etapa(self):
        return 'coordenacao'

class CoordenadorApprovalStrategy(ApprovalStrategy):
    def can_approve(self, user, esteira_item):
        return (esteira_item.etapa_atual == 'coordenacao'
                and esteira_item.status == 'em_andamento')
    def get_next_etapa(self):
        return 'tesouraria'
```

### Tarefa 7.3: Serializers e ViewSet da Esteira

**EsteiraListSerializer**: campos conforme o Dashboard do Analista (PDFs 006/007): `id`, `ordem` (prioridade), `contrato` (nested: codigo, associado nome, cpf_cnpj, matricula), `data_assinatura`, `valor_disponivel`, `comissao_agente`, `status_contrato`, `status_documentacao` (calculated), `contato_web` (bool), `termos_web` (bool), `agente` (nested: full_name), `orgao_publico`, `documentos_count`, `acoes_disponiveis` (list de ações válidas para o estado atual).

**EsteiraViewSet** com ações customizadas:

```python
class EsteiraViewSet(GenericViewSet, ListModelMixin, RetrieveModelMixin):
    @action(detail=True, methods=['post'])
    def assumir(self, request, pk=None):
        """POST /api/v1/esteira/{id}/assumir/"""

    @action(detail=True, methods=['post'])
    def aprovar(self, request, pk=None):
        """POST /api/v1/esteira/{id}/aprovar/"""

    @action(detail=True, methods=['post'])
    def pendenciar(self, request, pk=None):
        """POST /api/v1/esteira/{id}/pendenciar/
        Body: { tipo: string, descricao: string }"""

    @action(detail=True, methods=['post'])
    def validar_documento(self, request, pk=None):
        """POST /api/v1/esteira/{id}/validar-documento/"""

    @action(detail=True, methods=['post'])
    def solicitar_correcao(self, request, pk=None):
        """POST /api/v1/esteira/{id}/solicitar-correcao/
        Body: { observacao: string }"""

    @action(detail=True, methods=['get'])
    def transicoes(self, request, pk=None):
        """GET /api/v1/esteira/{id}/transicoes/ — histórico"""
```

### Tarefa 7.4: Dashboard do Analista (Frontend)

Criar `src/app/(dashboard)/analise/page.tsx` reproduzindo o layout dos PDFs 006/007:

**Barra de filtros no topo:**
- Input "BUSCAR POR NOME (EX.: AF...)" à esquerda
- Select de filtro: "Ativos (exceto Concluídos)" como opção padrão, com opções: Todos, Ativos, Pendentes, Concluídos
- Select de paginação: "20/página"
- Botão "Filtrar"

**Tabela principal:**
Colunas conforme o PDF do Dashboard Analista:

| Coluna | Renderização |
|--------|--------------|
| Assumir | Botão "Assumir" (verde) — só aparece se ninguém assumiu |
| Ordem | Número de prioridade |
| Código | Código do contrato (CTR-XXXX...) em monospace |
| CPF/Matr. | CPF do associado + matrícula |
| Associado | Nome completo |
| Assinatura | Data formatada dd/mm/yyyy |
| Disponível (R$) | Valor formatado em reais |
| Comissão Agente (10%) | Valor da comissão |
| Status Contrato | StatusBadge (Pendente, Concluído) |
| Status Documentação | StatusBadge especial: "Reenvio pendente" (amarelo), "Incompleta" (rosa/vermelho) |
| Contato | Badge "WEB" (indicando se contato foi feito via web) |
| Termos | Badge "WEB" (indicando se termos foram assinados via web) |
| Agente | Nome do agente |
| Órgão Público | Nome do órgão + matrícula do servidor |
| Docs/Formulário | Botão "Ver documentos / formulário (N)" com contagem |
| Ações | Botões conforme estado: "Validar documento revisto" (verde, quando doc reenviado), "Solicitar correção novamente" (outline) |

**Interação "Assumir":**
Ao clicar "Assumir", exibe Dialog de confirmação: "Deseja assumir a análise do contrato {código} do associado {nome}?". Ao confirmar, POST /api/v1/esteira/{id}/assumir/. A row atualiza para mostrar ações de aprovação.

**Interação "Validar documento revisto":**
Abre Dialog com preview dos documentos (links para download). Botões: "Aprovar documentação" (POST aprovar), "Solicitar nova correção" (POST solicitar-correcao com campo textarea para observação).

### Tarefa 7.5: Esteira de Pendências do Agente (Frontend)

Criar `src/app/(dashboard)/agentes/esteira-pendencias/page.tsx` conforme PDF Capture 004:

**Filtro no topo:**
- Input "Nome / Código do contrato / CPF" com placeholder
- Botões: "Filtrar" (primary), "Limpar" (outline), "← Voltar" (outline)

**Lista de pendências:**
Tabela com campos: Associado, Matrícula, Tipo de Pendência, Descrição, Data, Ações. Quando não há pendências: estado vazio com EmptyState "Nenhuma pendência aberta no momento."

Paginação com "Pesquisar por nome..." + select "Por página: 5" + "Mostrando X-Y de Z".

**Validação Bloco 7**: Analista vê lista de contratos na esteira. Clica "Assumir" → contrato fica "em_andamento" com analista vinculado. Pode aprovar (move para coordenação) ou pendenciar (move para agente com motivo). Agente vê pendências na tela de esteira. Estado da máquina é consistente (sem transições inválidas).

---

## BLOCO 8 — Contratos do Agente (Dia 14)

### Tarefa 8.1: Contratos Backend

Criar ViewSet em `apps/contratos/views.py`:

```python
class ContratoViewSet(ReadOnlyModelViewSet):
    """
    Contratos do agente logado. Read-only pois contratos são criados
    via cadastro de associado e efetivados pela tesouraria.
    """
    def get_queryset(self):
        qs = Contrato.objects.select_related('associado', 'agente')
        if self.request.user.has_role('AGENTE'):
            qs = qs.filter(agente=self.request.user)
        return qs.prefetch_related('ciclos__parcelas')

    @action(detail=False, methods=['get'])
    def resumo(self, request):
        """GET /api/v1/contratos/resumo/
        Retorna: { total: 130, concluidos: 73, pendentes: 57 }"""
```

### Tarefa 8.2: Tela "Meus Contratos" do Agente (Frontend)

Criar `src/app/(dashboard)/agentes/meus-contratos/page.tsx` conforme PDFs 002/003:

**Seção 1 — Resumo (3 cards):**
Três cards em grid: "130 Contratos cadastrados", "73 Concluídos (status do contrato)", "57 Pendentes (status do contrato)". Fundo escuro, números grandes, labels muted.

**Seção 2 — Filtros:**
- Input "Pesquisar por nome..."
- Select "Mensalidades": Todas, 1/3, 2/3, 3/3
- Select "Por página": 10, 20, 50
- Label "Mostrando 1-10 de 130"

**Seção 3 — Tabela de contratos:**

| Coluna | Renderização |
|--------|--------------|
| Associado | Nome + ID (#XXX) |
| Órgão / Matrícula | Nome do órgão + matrícula do servidor |
| Status do Contrato | StatusBadge: Pendente (laranja), Concluído (verde) |
| Mensalidade | R$ formatado |
| Auxílio do Agente | R$ formatado + "10% de margem" |
| Mensalidades (x/3) | "3/3" com detalhes expandidos: "Mensalidades efetivadas, Auto: 2 Manual: 1" + badges: "Apto a refinanciamento (3/3)" (verde) OU "CPF já possui refinanciamento" (amarelo com cadeado) |
| Liberação do Auxílio | Badge "Pago" (verde) + data |
| Ações | Botão "Solicitar refinanciamento" (habilitado se 3/3 e sem refin. ativo) OU ícone cadeado "CPF já possui refinanciamento" (disabled) |

Paginação completa: "< Anterior | Página 1 de 13 | Próxima >".

**Validação Bloco 8**: Agente vê seus contratos com resumo correto. Filtro por mensalidades funciona. Badges de "Apto a refinanciamento" e "CPF já possui" aparecem conforme regras. Paginação server-side.

---

## Checklist Final da Semana 2

- [ ] Serializers: AssociadoList, AssociadoDetail, AssociadoCreate, AssociadoUpdate, AssociadoMetricas
- [ ] AssociadoFilter com 8 filtros
- [ ] AssociadoService com calcular_metricas() e criar_associado_completo()
- [ ] AssociadoFactory (PF e PJ)
- [ ] ValidationStrategy (Cadastro e Edição)
- [ ] AssociadoViewSet com metricas, ciclos, documentos
- [ ] Frontend: listagem com 4 StatsCards, tabela, row expansível com ciclos
- [ ] Frontend: formulário multi-step de 5 etapas com todos os componentes customizados
- [ ] Frontend: detalhe e edição do associado
- [ ] EsteiraService como state machine com transições validadas
- [ ] ApprovalStrategy (Analista e Coordenador)
- [ ] EsteiraViewSet com assumir, aprovar, pendenciar, validar-documento, solicitar-correcao
- [ ] Frontend: Dashboard Analista com tabela completa e ações
- [ ] Frontend: Esteira de Pendências do Agente
- [ ] Frontend: Dialog de confirmação para assumir e aprovar
- [ ] ContratoViewSet com resumo
- [ ] Frontend: Meus Contratos com resumo, filtros, tabela com badges de refinanciamento
- [ ] Transições de Transicao registradas para audit trail
- [ ] Fluxo end-to-end: Agente cadastra → aparece na esteira do Analista → Analista assume e aprova
- [ ] POST de criação é atômico (transaction.atomic)
- [ ] Kubb regenerado com novos endpoints (pnpm --filter @abase/web generate:api)
