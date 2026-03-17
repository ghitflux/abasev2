# PROMPT SEMANA 3 — Tesouraria + Confirmações + Refinanciamento + Coordenação

> Prompt para Claude Code executar a Semana 3 do ABASE v2.
> Pré-requisito: Semana 2 completa (CRUD Associados, Esteira funcional, Contratos do Agente).
> Blocos 9 a 12, continuando numeração sequencial.

## Contexto da Semana

A Semana 3 implementa a parte financeira e de controle do sistema: o Dashboard do Tesoureiro com efetivação de contratos via PIX, o módulo de Confirmações (ligação telefônica e averbação junto aos órgãos), e todo o fluxo de refinanciamento controlado pela Coordenação. Ao final desta semana, o ciclo completo desde a aprovação na esteira até a efetivação financeira estará funcional.

---

## BLOCO 9 — Tesouraria Backend + Frontend (Dia 15-16)

### Tarefa 9.1: TesourariaService

Criar em `apps/tesouraria/services.py`:

```python
# apps/tesouraria/services.py
class TesourariaService:
    """
    Gerencia o fluxo financeiro de efetivação de contratos.
    Contratos chegam aqui após aprovação pela Coordenação na esteira.
    O tesoureiro efetiva o contrato anexando comprovante PIX, ou congela se houver problema.
    """

    @staticmethod
    def listar_contratos_pendentes(mes=None):
        """
        Retorna contratos na etapa tesouraria da esteira, separados em:
        - Pendentes de pagamento (status contrato = pendente, esteira = tesouraria)
        - Pagos/Cancelados (status contrato = concluido ou cancelado)
        Filtra por mês de competência se informado.
        Conforme PDF Capture 009: Nome, CPF/CNPJ, Comprovante (Associado + Agente),
        Ação (Ver Cadastro Web / Congelar contrato), Chave PIX, Cód. Contrato,
        Data/Hora, Status, Agente Responsável, Margem Disponível.
        """

    @staticmethod
    def efetivar_contrato(contrato_id, comprovante_associado, comprovante_agente, user):
        """
        Efetiva o contrato com upload de 2 comprovantes PIX.
        Regras:
        1. Contrato deve estar com status 'pendente' e na etapa 'tesouraria' da esteira
        2. Dois comprovantes obrigatórios: um do associado, um do agente
        3. Ao efetivar: contrato.status = 'concluido', associado.status = 'ativo'
        4. Atualiza EsteiraItem para etapa='concluido', status='aprovado'
        5. Cria Transicao com observação "Contrato efetivado pela tesouraria"
        6. Salva os comprovantes no model Comprovante
        """

    @staticmethod
    def congelar_contrato(contrato_id, motivo, user):
        """
        Congela contrato temporariamente (não rejeita, apenas pausa).
        Cria registro de Transicao com motivo.
        """

    @staticmethod
    def obter_dados_bancarios(contrato_id):
        """
        Retorna dados bancários do associado para o tesoureiro
        realizar a transferência PIX: banco, agência, conta, tipo, chave PIX.
        """
```

### Tarefa 9.2: Serializers da Tesouraria

```python
# apps/tesouraria/serializers.py

class TesourariaContratoListSerializer(Serializer):
    """
    Serializer para a tabela do Dashboard do Tesoureiro (PDF 009).
    Campos conforme a tela: nome, cpf_cnpj, comprovantes (status),
    ação, chave_pix, codigo_contrato, data_hora, status, agente, margem_disponivel.
    """
    id = IntegerField()
    nome = CharField(source='associado.nome_completo')
    cpf_cnpj = CharField(source='associado.cpf_cnpj')
    chave_pix = CharField(source='associado.dados_bancarios.chave_pix')
    codigo = CharField()
    data_assinatura = DateField()
    status = CharField()
    agente_nome = CharField(source='agente.full_name')
    margem_disponivel = DecimalField(max_digits=10, decimal_places=2)
    comprovantes = ComprovanteResumoSerializer(many=True)
    dados_bancarios = DadosBancariosSerializer(source='associado.dados_bancarios')

class EfetivarContratoSerializer(Serializer):
    """Recebe os 2 comprovantes PIX para efetivação."""
    comprovante_associado = FileField(required=True)
    comprovante_agente = FileField(required=True)
```

### Tarefa 9.3: ViewSet da Tesouraria

```python
# apps/tesouraria/views.py
class TesourariaContratoViewSet(GenericViewSet, ListModelMixin, RetrieveModelMixin):
    """Endpoints do Dashboard do Tesoureiro."""
    permission_classes = [IsAuthenticated, IsTesoureiro]

    def get_queryset(self):
        return Contrato.objects.filter(
            esteira_items__etapa_atual='tesouraria'
        ).select_related('associado', 'associado__dados_bancarios', 'agente')

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser])
    def efetivar(self, request, pk=None):
        """POST /api/v1/tesouraria/contratos/{id}/efetivar/
        Body: multipart com comprovante_associado e comprovante_agente."""

    @action(detail=True, methods=['post'])
    def congelar(self, request, pk=None):
        """POST /api/v1/tesouraria/contratos/{id}/congelar/
        Body: { motivo: string }"""

    @action(detail=True, methods=['get'])
    def dados_bancarios(self, request, pk=None):
        """GET /api/v1/tesouraria/contratos/{id}/dados-bancarios/
        Retorna dados PIX do associado para transferência."""
```

### Tarefa 9.4: Dashboard do Tesoureiro (Frontend)

Criar `src/app/(dashboard)/tesouraria/page.tsx` conforme PDF Capture 009:

**Barra superior:** Label "Tessoureiro: {nome}" + "Sair". Select de mês (CalendarCompetencia): "março de 2026". Botões de ação rápida: "Baixar relatório do dia específico" (DatePicker popup), "Baixar PDF", "Baixar relatório do dia", "Impressão digitada (nova)".

**Seção de filtros:** Select "Pagamento: Todos" + DatePicker "Início" + DatePicker "Fim" + Input "Buscar por nome, CPF/CNPJ ou Código do Contrato" + Botão "Aplicar" (verde) + Badge "Pendentes: 2" (rosa, clicável para filtrar apenas pendentes).

**Tabela de Contratos (seção PENDENTES):**

| Coluna | Renderização |
|--------|--------------|
| Nome | Nome completo do associado |
| CPF/CNPJ | Formatado com máscara |
| Comprovante | Dois slots de upload: "Comprovante Associado" + "Comprovante Agente" usando FileUploadDropzone pequeno. Quando enviado, mostra link "Ver comprovante (Associado/Agente)". Botão "Limpar" (vermelho) para remover |
| Ação | Dois botões: "Ver Cadastro (Web)" (link para detalhe do associado) + "Congelar contrato" (laranja, abre Dialog com textarea para motivo) |
| Chave PIX | Texto ou "—" se não cadastrado |
| Cód. Contrato | CTR-XXXXX em monospace |
| Data/Hora | dd/mm/yyyy HH:mm |
| Status | StatusBadge: "Pendente" (laranja) |
| Agente Responsável | Nome do agente |
| Margem Disponível (R$) | Valor formatado |
| Botão "Dados bancários" | Botão verde que abre Dialog mostrando: Banco, Agência, Conta, Tipo, Chave PIX |

**Seção "PAGOS/CANCELADOS"** (abaixo, com header amarelo): mesma tabela mas com status "Concluído" (verde) e comprovantes já anexados mostrando "Ver comprovante" ao invés de upload.

**Paginação:** "Mostrando 1-5 de 16" + botões numéricos de página.

**Interação de efetivação:** O tesoureiro clica em "Dados bancários" → vê os dados PIX → realiza a transferência externamente → volta e faz upload dos 2 comprovantes na row → ao ter ambos comprovantes, aparece indicação visual de que pode efetivar. O sistema efetiva automaticamente ao receber ambos os comprovantes (ou pode ter botão explícito "Efetivar" que aparece quando ambos estão presentes).

---

## BLOCO 10 — Confirmações: Ligação & Averbação (Dia 17-18)

### Tarefa 10.1: Backend de Confirmações

Criar/expandir `apps/tesouraria/services.py`:

```python
class ConfirmacaoService:
    """
    Gerencia o fluxo de confirmação telefônica e averbação.
    Para cada associado ativo em uma competência, o tesoureiro deve:
    1. Registrar o link da ligação (gravação da chamada)
    2. Confirmar que a ligação foi realizada
    3. Confirmar que a averbação junto ao órgão público foi feita
    Conforme PDF Capture 010.
    """

    @staticmethod
    def listar_por_competencia(competencia):
        """
        Retorna todos os associados ativos para a competência informada,
        com status de ligação e averbação.
        """

    @staticmethod
    def salvar_link_chamada(confirmacao_id, link):
        """Salva URL da gravação da chamada (ex: https://nuvidio.me/rfc2j6)."""

    @staticmethod
    def confirmar_ligacao(confirmacao_id, user):
        """Marca ligação como confirmada/recebida."""

    @staticmethod
    def confirmar_averbacao(confirmacao_id, user):
        """Marca averbação junto ao órgão como confirmada."""
```

Endpoints:
```
GET  /api/v1/tesouraria/confirmacoes/?competencia=2026-03  → lista por mês
POST /api/v1/tesouraria/confirmacoes/{id}/link/             → { link: string }
POST /api/v1/tesouraria/confirmacoes/{id}/confirmar-ligacao/
POST /api/v1/tesouraria/confirmacoes/{id}/confirmar-averbacao/
```

### Tarefa 10.2: Tela de Confirmações (Frontend)

Criar `src/app/(dashboard)/tesouraria/confirmacoes/page.tsx` conforme PDF Capture 010:

**Header:** Título "Confirmações — Ligação & Averbação". Subtítulo "cole o link de atendimento, confirme ligação e averbação."

**Filtro:** CalendarCompetencia (MonthPicker) mostrando "março de 2026". Input "Buscar por nome" + Botão "Buscar".

**Tabela de Confirmações:**

| Coluna | Renderização |
|--------|--------------|
| Nome | Nome completo do associado (em caps conforme tela legada) |
| Link de Chamada | Input de texto inline "Inserir link (texto livre)" + Botão "Salvar" (ícone check) + Botão "Abrir" (ícone external link, quando tem link). Abaixo do input: indicator "Sem link ainda" (bolinha vermelha) OU "Ligação recebida" (bolinha verde + check) |
| Averbação | Botão "Confirmar averbação" (outline). Quando confirmada: "Averbação confirmada" (texto verde com check). Quando ligação não confirmada: botão "Confirmar ligação" aparece primeiro |

**Estados visuais por row (3 estados possíveis):**
1. **Sem link ainda** (vermelho): Input vazio, botão "Confirmar ligação" desabilitado, "Confirmar averbação" desabilitado
2. **Ligação recebida** (verde): Link salvo, botão "Confirmar ligação" clicado, "Confirmar averbação" habilitado
3. **Averbação confirmada** (verde completo): Tudo confirmado, linha marcada como concluída

A interação é sequencial: primeiro salvar link → depois confirmar ligação → depois confirmar averbação. Cada passo habilita o próximo.

---

## BLOCO 11 — Refinanciamento + Coordenação Backend (Dia 19-20)

### Tarefa 11.1: RefinanciamentoService

Criar em `apps/refinanciamento/services.py`:

```python
class RefinanciamentoService:
    """
    Gerencia o fluxo de refinanciamento de contratos.
    Um associado é elegível quando:
    1. Ciclo atual com 3/3 parcelas pagas (status=descontado)
    2. Possui 3 mensalidades livres reais (sem refinanciamento ativo)
    3. Não possui refinanciamento pendente/ativo para o mesmo CPF
    
    Fluxo: Agente solicita → Coordenador aprova/bloqueia → Tesouraria efetiva
    """

    @staticmethod
    def verificar_elegibilidade(contrato_id):
        """
        Verifica se o contrato é elegível para refinanciamento.
        Retorna: { elegivel: bool, motivo: str, parcelas_pagas: int,
                   mensalidades_livres: int, tem_refinanciamento_ativo: bool }
        """

    @staticmethod
    def solicitar(contrato_id, user):
        """
        Agente solicita refinanciamento.
        Valida elegibilidade → Cria registro Refinanciamento (status=pendente_apto)
        → Cria novo Ciclo destino (status=futuro) → Notifica coordenação
        """

    @staticmethod
    def aprovar(refinanciamento_id, user):
        """
        Coordenador aprova refinanciamento.
        Muda status para 'concluido'.
        Ativa o novo ciclo (status=aberto) com 3 novas parcelas.
        """

    @staticmethod
    def bloquear(refinanciamento_id, motivo, user):
        """Coordenador bloqueia. Status = 'bloqueado' com motivo."""

    @staticmethod
    def reverter(refinanciamento_id, user):
        """Reverte refinanciamento aprovado. Status = 'revertido'."""
```

### Tarefa 11.2: EligibilityStrategy

```python
# apps/refinanciamento/strategies.py
class EligibilityStrategy(ABC):
    """Strategy para verificação de elegibilidade de refinanciamento."""
    @abstractmethod
    def is_eligible(self, contrato) -> tuple[bool, str]: ...

class StandardEligibilityStrategy(EligibilityStrategy):
    """Regra padrão: 3/3 pagas + 3 mensalidades livres + sem refin. ativo."""
    def is_eligible(self, contrato):
        ciclo_atual = contrato.ciclos.filter(status='aberto').first()
        if not ciclo_atual:
            return False, "Nenhum ciclo aberto encontrado"

        parcelas_pagas = ciclo_atual.parcelas.filter(status='descontado').count()
        if parcelas_pagas < 3:
            return False, f"Apenas {parcelas_pagas}/3 parcelas pagas"

        # Verificar se já tem refinanciamento ativo para o CPF
        tem_ativo = Refinanciamento.objects.filter(
            contrato__associado__cpf_cnpj=contrato.associado.cpf_cnpj,
            status__in=['pendente_apto', 'concluido']
        ).exists()
        if tem_ativo:
            return False, "CPF já possui refinanciamento ativo"

        return True, "Apto a refinanciamento (3/3)"
```

### Tarefa 11.3: ViewSets de Refinanciamento

```python
# apps/refinanciamento/views.py
class RefinanciamentoViewSet(GenericViewSet, ListModelMixin, RetrieveModelMixin):
    """
    Endpoints de refinanciamento.
    Agente: vê seus refinanciados e solicita novos.
    Coordenador: vê todos, aprova ou bloqueia.
    """

    @action(detail=True, methods=['post'])
    def solicitar(self, request, pk=None):
        """POST /api/v1/refinanciamentos/{contrato_id}/solicitar/ — Agente solicita"""

    @action(detail=True, methods=['post'])
    def aprovar(self, request, pk=None):
        """POST /api/v1/refinanciamentos/{id}/aprovar/ — Coordenador aprova"""

    @action(detail=True, methods=['post'])
    def bloquear(self, request, pk=None):
        """POST /api/v1/refinanciamentos/{id}/bloquear/ — Body: { motivo: string }"""

class CoordenadorRefinanciamentoViewSet(GenericViewSet, ListModelMixin):
    """
    Visão do Coordenador para gestão de refinanciamentos.
    Dois modos conforme PDFs 013/014:
    - Refinanciados: lista quem já foi refinanciado (aprovados)
    - Refinanciamento: lista pendentes (aguardando aprovação)
    Filtros: janela temporal (Anterior/Hoje/Próximo), ano, agente, mensalidades, busca.
    """
    permission_classes = [IsAuthenticated, (IsCoordenador | IsAdmin)]

    @action(detail=False, methods=['get'])
    def refinanciados(self, request):
        """GET /api/v1/coordenacao/refinanciados/
        Lista refinanciamentos concluídos com dados de ciclo e auditoria.
        Conforme PDF 013: #, Associado, CPF/CNPJ, JAN/FEV/MAR (meses do ciclo),
        Data do Ciclo, Mensalidades, Refinanciamento (badge numérico), Auditoria."""

    @action(detail=False, methods=['get'])
    def refinanciamento(self, request):
        """GET /api/v1/coordenacao/refinanciamento/
        Lista pendentes: associados com solicitação do Analista + 3 mensalidades livres.
        Conforme PDF 014: Agente, Associado, CPF/CNPJ, meses do ciclo,
        Mensalidades, Refinanciamento, Ação (pendente-APTO / Bloqueado)."""
```

### Tarefa 11.4: Tela Refinanciados do Agente (Frontend)

Criar `src/app/(dashboard)/agentes/refinanciados/page.tsx` conforme PDF Capture 005 (sistema legado) adaptado para o novo design (Image 1 style):

**Resumo (4 cards):** "36 Total" | "10 Concluídos" | "0 Falharam" | "0 Revertidos"

**Filtros:** Input "Buscar por nome, CPF, contrato ou ciclo..." + Select "Todos status" + Input "cycle_key (ex: 2025-10|2025-11|2025-12)" + Select "Por página: 15" + Botão "Aplicar" + Botão "Limpar".

**Tabela de Refinanciados:**

| Coluna | Renderização |
|--------|--------------|
| Contrato | Código CTR-XXXX em monospace |
| Ciclo | Datas do ciclo (2025-10\|2025-11\|2025-12) |
| Refs | 3 meses separados (10/2025, 11/2025, 12/2025) |
| Executado em | Data/hora (ou "N/I" se não executado) |
| Status | StatusBadge: "enabled" (verde) |
| Comprovantes (Agente) | Badge "0 anexo" (amarelo) OU "1 anexo(s)" (azul) com nome do arquivo e botão "Ver" |

### Tarefa 11.5: Telas do Coordenador (Frontend)

**Coordenador — Refinanciados** (`src/app/(dashboard)/coordenacao/refinanciados/page.tsx`) conforme PDF 013:

Header com toggle: botão "Refinanciados" (ativo, verde) e "Refinanciamento" (inativo). Botão "Imprimir / PDF".

Navegação temporal: "Janela:" + Botões "< Anterior" | "Hoje" | "Próximo >" | "Imprimir auditoria". Exibe o ciclo atual: "Refinanciados — 2026-01-01|2026-02-01|2026-03-01". Label: "Modo: somente refinanciados (refinanciamentos)". Contadores: "Total: 323 | Filtrados: 323 | Exibindo: 323".

Filtros: Select "Ano: Todos" + Input "Buscar por nome ou CPF/CI" + Label "Agente: Todos | Mensalidades: 0/3".

Tabela:

| Coluna | Renderização |
|--------|--------------|
| # | Número sequencial |
| Associado | Nome completo (CAPS) |
| CPF/CNPJ | Formatado |
| JAN/2026 1ª | Data da competência do 1º mês |
| FEV/2026 2ª | Data da competência do 2º mês |
| MAR/2026 3ª | Data da competência do 3º mês |
| Data do Ciclo | Timestamp (dd/mm/yyyy HH:mm) |
| Mensalidades | "3/3" ou "2/3" |
| Refinanciamento | Badge numérico (1, 2, etc.) — quantos refinanciamentos já fez |
| Auditoria | Ícone/botão para ver detalhes de auditoria |

**Coordenador — Refinanciamento** (`src/app/(dashboard)/coordenacao/refinanciamento/page.tsx`) conforme PDF 014:

Mesma estrutura de header e navegação temporal. Label: "Condição: somente com solicitação do Analista (pendente) + 3 mensalidades livres reais". Contadores: "Total: 566 | Filtrados: 566 | Exibindo: 566 | Aptos: 1".

Filtros adicionais: Select "Agente: Todos" + Select "Mensalidades: Todas".

Tabela com coluna de ação:

| Coluna | Renderização |
|--------|--------------|
| Agente | Nome do agente |
| Associado | Nome completo |
| CPF/CNPJ | Formatado |
| JAN/FEV/MAR | Datas dos meses do ciclo |
| Mensalidades | "3/3" |
| Refinanciamento | Badge numérico |
| Ação | StatusBadge dinâmico: "pendente – APTO" (verde, clicável para aprovar) OU "Bloqueado" (cinza com cadeado). Ao clicar APTO → Dialog de confirmação → POST aprovar. Ao clicar Bloqueado → Dialog com motivo |

### Tarefa 11.6: Refinanciamentos do Tesoureiro (Frontend)

Criar `src/app/(dashboard)/tesouraria/refinanciamentos/page.tsx` conforme PDFs 011/012:

**Filtros:** Select "Exibir: Todos" + Input "CPF ou nome.." + DatePicker "Início" + DatePicker "Fim" + Botão "Aplicar". Botões de relatório: "PDF do dia", "Impressão digitada", "PDF período".

**Tabela:**

| Coluna | Renderização |
|--------|--------------|
| Valor Refinanciamento | R$ formatado |
| Agente (Repasse) | R$ (10% do valor) + "10% do valor" label |
| Pagamento | StatusBadge: "Pendente" (laranja) — "Aguardando anexação / conferência" + timestamp |
| Itens | Badge "Itens (3)" — clicável, abre lista de itens do refinanciamento |
| Solicitação | Status "Em progresso" (amarelo) com timestamp "Solicitado em: dd/mm/yyyy HH:mm" |
| Comprovantes | Dois slots: "Comprovantes (Associado / Agente)" com FileUploadDropzone |

**Validação Bloco 9-11**: Tesoureiro vê contratos pendentes. Faz upload de comprovantes → contrato efetivado → associado ativo. Confirmações funcionam sequencialmente (link → ligação → averbação). Agente solicita refinanciamento → aparece na tela do Coordenador → Coordenador aprova ou bloqueia.

---

## BLOCO 12 — Testes de Integração da Semana (Dia 21)

### Tarefa 12.1: Testes do Fluxo Completo

Criar testes que validem o fluxo end-to-end:

```python
# tests/test_fluxo_completo.py
class TestFluxoCompleto(TestCase):
    """Testa o fluxo desde cadastro até refinanciamento."""

    def test_fluxo_cadastro_ate_efetivacao(self):
        """1. Agente cadastra → 2. Analista aprova → 3. Coord aprova → 4. Tesoureiro efetiva"""

    def test_pendenciamento_e_retorno(self):
        """1. Agente cadastra → 2. Analista pendencia → 3. Agente corrige → 4. Volta para esteira"""

    def test_refinanciamento_completo(self):
        """1. Associado com 3/3 pagas → 2. Agente solicita → 3. Coord aprova → 4. Novo ciclo"""

    def test_refinanciamento_bloqueado_cpf_duplicado(self):
        """Tenta refinanciar CPF que já tem refinanciamento ativo → Bloqueado"""

    def test_efetivacao_sem_comprovante_falha(self):
        """Tenta efetivar sem ambos comprovantes → Erro 400"""

    def test_confirmacao_sequencial(self):
        """Ligação antes de averbação. Averbação sem ligação → Erro."""
```

---

## Checklist Final da Semana 3

- [ ] TesourariaService com efetivar, congelar, dados_bancarios
- [ ] Upload de 2 comprovantes PIX (associado + agente)
- [ ] Dashboard Tesoureiro com seções Pendentes e Pagos/Cancelados
- [ ] Filtros por mês, período, nome, CPF, código
- [ ] Dados bancários em Dialog popup
- [ ] ConfirmacaoService com link, ligação, averbação
- [ ] Tela Confirmações com interação sequencial (3 estados)
- [ ] CalendarCompetencia funcionando para filtro por mês
- [ ] RefinanciamentoService com verificar_elegibilidade, solicitar, aprovar, bloquear
- [ ] EligibilityStrategy com regra de 3/3 + 3 mensalidades livres + sem duplicata CPF
- [ ] Tela Refinanciados do Agente com resumo e tabela
- [ ] Tela Coordenador Refinanciados com navegação temporal e auditoria
- [ ] Tela Coordenador Refinanciamento com ações APTO/Bloqueado
- [ ] Tela Refinanciamentos do Tesoureiro com itens e comprovantes
- [ ] Geração de relatórios PDF (do dia, período)
- [ ] Testes de integração do fluxo completo
- [ ] Transições registradas em Transicao para audit trail
