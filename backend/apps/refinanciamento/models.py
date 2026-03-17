from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models

from core.models import BaseModel


class Refinanciamento(BaseModel):
    class Origem(models.TextChoices):
        LEGADO = "legado", "Legado"
        OPERACIONAL = "operacional", "Operacional"

    class Status(models.TextChoices):
        APTO_A_RENOVAR = "apto_a_renovar", "Apto a renovar"
        EM_ANALISE_RENOVACAO = "em_analise_renovacao", "Em análise para renovação"
        APROVADO_PARA_RENOVACAO = "aprovado_para_renovacao", "Aprovado para renovação"
        PENDENTE_APTO = "pendente_apto", "Pendente apto"
        BLOQUEADO = "bloqueado", "Bloqueado"
        CONCLUIDO = "concluido", "Concluído"
        DESATIVADO = "desativado", "Desativado"
        REVERTIDO = "revertido", "Revertido"
        EFETIVADO = "efetivado", "Efetivado"
        SOLICITADO = "solicitado", "Solicitado"
        EM_ANALISE = "em_analise", "Em análise"
        APROVADO = "aprovado", "Aprovado"
        REJEITADO = "rejeitado", "Rejeitado"

    associado = models.ForeignKey(
        "associados.Associado",
        on_delete=models.PROTECT,
        related_name="refinanciamentos",
    )
    contrato_origem = models.ForeignKey(
        "contratos.Contrato",
        on_delete=models.PROTECT,
        related_name="refinanciamentos",
        null=True,
        blank=True,
    )
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="refinanciamentos_solicitados",
    )
    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="refinanciamentos_aprovados",
        null=True,
        blank=True,
    )
    bloqueado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="refinanciamentos_bloqueados",
        null=True,
        blank=True,
    )
    efetivado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="refinanciamentos_efetivados",
        null=True,
        blank=True,
    )
    ciclo_origem = models.ForeignKey(
        "contratos.Ciclo",
        on_delete=models.PROTECT,
        related_name="refinanciamentos_origem",
        null=True,
        blank=True,
    )
    ciclo_destino = models.OneToOneField(
        "contratos.Ciclo",
        on_delete=models.PROTECT,
        related_name="refinanciamento_destino",
        null=True,
        blank=True,
    )
    competencia_solicitada = models.DateField()
    status = models.CharField(
        max_length=40, choices=Status.choices, default=Status.PENDENTE_APTO
    )
    valor_refinanciamento = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    repasse_agente = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    executado_em = models.DateTimeField(null=True, blank=True)
    data_ativacao_ciclo = models.DateTimeField(null=True, blank=True, db_index=True)
    legacy_refinanciamento_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
    )
    origem = models.CharField(
        max_length=20,
        choices=Origem.choices,
        default=Origem.OPERACIONAL,
    )
    motivo_bloqueio = models.TextField(blank=True)
    observacao = models.TextField(blank=True)
    # Campos herdados do legado (refinanciamentos + refinanciamento_solicitacoes)
    mode = models.CharField(max_length=20, default="manual")
    cycle_key = models.CharField(max_length=32, blank=True)
    ref1 = models.DateField(null=True, blank=True)
    ref2 = models.DateField(null=True, blank=True)
    ref3 = models.DateField(null=True, blank=True)
    ref4 = models.DateField(null=True, blank=True)
    cpf_cnpj_snapshot = models.CharField(max_length=20, blank=True)
    nome_snapshot = models.CharField(max_length=200, blank=True)
    agente_snapshot = models.CharField(max_length=200, blank=True)
    filial_snapshot = models.CharField(max_length=200, blank=True)
    contrato_codigo_origem = models.CharField(max_length=80, blank=True)
    contrato_codigo_novo = models.CharField(max_length=80, blank=True)
    parcelas_ok = models.PositiveSmallIntegerField(default=0)
    parcelas_json = models.JSONField(null=True, blank=True)
    analista_note = models.TextField(blank=True)
    coordenador_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="refinanciamentos_revisados",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    termo_antecipacao_path = models.CharField(max_length=255, blank=True)
    termo_antecipacao_original_name = models.CharField(max_length=255, blank=True)
    termo_antecipacao_mime = models.CharField(max_length=120, blank=True)
    termo_antecipacao_size_bytes = models.BigIntegerField(null=True, blank=True)
    termo_antecipacao_uploaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.associado.nome_completo} - {self.status}"


class Comprovante(BaseModel):
    class Tipo(models.TextChoices):
        PIX = "pix", "PIX"
        CONTRATO = "contrato", "Contrato"
        TERMO_ANTECIPACAO = "termo_antecipacao", "Termo de antecipação"
        COMPROVANTE_PAGAMENTO_ASSOCIADO = (
            "comprovante_pagamento_associado",
            "Comprovante pagamento associado",
        )
        COMPROVANTE_PAGAMENTO_AGENTE = (
            "comprovante_pagamento_agente",
            "Comprovante pagamento agente",
        )
        OUTRO = "outro", "Outro"

    class Papel(models.TextChoices):
        ASSOCIADO = "associado", "Associado"
        AGENTE = "agente", "Agente"
        OPERACIONAL = "operacional", "Operacional"

    class Origem(models.TextChoices):
        EFETIVACAO_CONTRATO = "efetivacao_contrato", "Efetivação do contrato"
        ANALISE_RENOVACAO = "analise_renovacao", "Análise da renovação"
        TESOURARIA_RENOVACAO = "tesouraria_renovacao", "Tesouraria da renovação"
        LEGADO = "legado", "Legado"
        OUTRO = "outro", "Outro"

    refinanciamento = models.ForeignKey(
        Refinanciamento,
        on_delete=models.CASCADE,
        related_name="comprovantes",
        null=True,
        blank=True,
    )
    contrato = models.ForeignKey(
        "contratos.Contrato",
        on_delete=models.CASCADE,
        related_name="comprovantes",
        null=True,
        blank=True,
    )
    ciclo = models.ForeignKey(
        "contratos.Ciclo",
        on_delete=models.CASCADE,
        related_name="comprovantes",
        null=True,
        blank=True,
    )
    tipo = models.CharField(max_length=40, choices=Tipo.choices, default=Tipo.PIX)
    papel = models.CharField(
        max_length=20, choices=Papel.choices, default=Papel.ASSOCIADO
    )
    arquivo = models.FileField(upload_to="refinanciamentos/")
    arquivo_referencia_path = models.CharField(max_length=500, blank=True)
    nome_original = models.CharField(max_length=255, blank=True)
    mime = models.CharField(max_length=120, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    data_pagamento = models.DateTimeField(null=True, blank=True)
    legacy_comprovante_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
    )
    origem = models.CharField(
        max_length=40, choices=Origem.choices, default=Origem.OUTRO
    )
    agente_snapshot = models.CharField(max_length=200, blank=True)
    filial_snapshot = models.CharField(max_length=200, blank=True)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="comprovantes_refinanciamento",
    )

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.arquivo and not self.arquivo_referencia_path:
            self.arquivo_referencia_path = getattr(self.arquivo, "name", "")
        if self.arquivo and not self.nome_original:
            self.nome_original = getattr(self.arquivo, "name", "")
        if self.arquivo and not self.mime:
            self.mime = getattr(self.arquivo, "content_type", "") or self.mime
        if self.arquivo and self.size_bytes is None:
            try:
                self.size_bytes = getattr(self.arquivo, "size", None)
            except OSError:
                self.size_bytes = None
        super().save(*args, **kwargs)

    @property
    def arquivo_referencia(self) -> str:
        if self.arquivo_referencia_path:
            return self.arquivo_referencia_path
        if not self.arquivo:
            return ""
        return str(getattr(self.arquivo, "name", "") or "")

    @property
    def arquivo_disponivel_localmente(self) -> bool:
        if not self.arquivo:
            return False
        arquivo_name = self.arquivo_referencia
        if not arquivo_name:
            return False
        try:
            return bool(default_storage.exists(arquivo_name))
        except Exception:
            return False

    def __str__(self) -> str:
        origem = self.refinanciamento_id or self.contrato_id
        return f"{self.tipo}:{self.papel}#{origem}"


class Assumption(BaseModel):
    """Fila de atendimento de refinanciamento pelo analista (refinanciamento_assumptions)."""

    class Status(models.TextChoices):
        LIBERADO = "liberado", "Liberado"
        ASSUMIDO = "assumido", "Assumido"
        FINALIZADO = "finalizado", "Finalizado"

    cadastro = models.ForeignKey(
        "associados.Associado",
        on_delete=models.PROTECT,
        related_name="refi_assumptions",
    )
    cpf_cnpj = models.CharField(max_length=20, blank=True)
    request_key = models.CharField(max_length=80)
    refs_json = models.JSONField(null=True, blank=True)
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="refi_assumptions_solicitadas",
    )
    analista = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="refi_assumptions_assumidas",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.LIBERADO
    )
    solicitado_em = models.DateTimeField(null=True, blank=True)
    liberado_em = models.DateTimeField(null=True, blank=True)
    assumido_em = models.DateTimeField(null=True, blank=True)
    finalizado_em = models.DateTimeField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Assumption #{self.pk} - {self.status}"


class AjusteValor(BaseModel):
    """Ajuste manual de valor em um refinanciamento (refinanciamento_ajustes_valor)."""

    refinanciamento = models.ForeignKey(
        Refinanciamento, on_delete=models.CASCADE, related_name="ajustes_valor"
    )
    cpf_cnpj = models.CharField(max_length=20, blank=True)
    origem = models.CharField(max_length=10, blank=True)
    fonte_base = models.CharField(max_length=10, blank=True)
    valor_base = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    valor_antigo = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    valor_novo = models.DecimalField(max_digits=12, decimal_places=2)
    tp_margem = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    ac_margem = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    a2_margem = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ajustes_valor_criados",
    )
    ip = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    motivo = models.TextField(blank=True)
    meta = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"AjusteValor #{self.pk} refi={self.refinanciamento_id}"


class Item(BaseModel):
    """Parcela/mês vinculada a um refinanciamento (refinanciamento_itens)."""

    refinanciamento = models.ForeignKey(
        Refinanciamento, on_delete=models.CASCADE, related_name="itens"
    )
    pagamento_mensalidade = models.ForeignKey(
        "importacao.PagamentoMensalidade",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refi_itens",
    )
    tesouraria_pagamento = models.ForeignKey(
        "tesouraria.Pagamento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refi_itens",
    )
    referencia_month = models.DateField()
    status_code = models.CharField(max_length=2, blank=True)
    valor = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    import_uuid = models.CharField(max_length=36, blank=True)
    source_file_path = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["refinanciamento_id", "referencia_month"]

    def __str__(self) -> str:
        return f"Item #{self.pk} refi={self.refinanciamento_id} ref={self.referencia_month}"
