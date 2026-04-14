from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import BaseModel


class BaixaManual(BaseModel):
    """Baixa manual de parcela pendente ou não descontada, com comprovante de pagamento."""

    parcela = models.OneToOneField(
        "contratos.Parcela",
        on_delete=models.PROTECT,
        related_name="baixa_manual",
    )
    realizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="baixas_manuais",
    )
    comprovante = models.FileField(upload_to="baixas_manuais/")
    nome_comprovante = models.CharField(max_length=255, blank=True)
    observacao = models.TextField(blank=True)
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2)
    data_baixa = models.DateField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"BaixaManual Parcela#{self.parcela_id} - {self.data_baixa}"


class LiquidacaoContrato(BaseModel):
    class OrigemSolicitacao(models.TextChoices):
        AGENTE = "agente", "Agente"
        COORDENACAO = "coordenacao", "Coordenação"
        ADMINISTRACAO = "administracao", "Administração"
        RENOVACAO = "renovacao", "Renovação"

    contrato = models.ForeignKey(
        "contratos.Contrato",
        on_delete=models.PROTECT,
        related_name="liquidacoes",
    )
    realizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="liquidacoes_realizadas",
    )
    data_liquidacao = models.DateField()
    valor_total = models.DecimalField(max_digits=12, decimal_places=2)
    comprovante = models.FileField(upload_to="liquidacoes_contrato/")
    nome_comprovante = models.CharField(max_length=255, blank=True)
    origem_solicitacao = models.CharField(
        max_length=20,
        choices=OrigemSolicitacao.choices,
        blank=True,
        default="",
    )
    observacao = models.TextField(blank=True)
    contrato_status_anterior = models.CharField(max_length=20, blank=True)
    associado_status_anterior = models.CharField(max_length=20, blank=True)
    revertida_em = models.DateTimeField(null=True, blank=True)
    revertida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="liquidacoes_revertidas",
    )
    motivo_reversao = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    @property
    def status(self) -> str:
        return "revertida" if self.revertida_em else "ativa"

    def __str__(self) -> str:
        return f"Liquidacao contrato#{self.contrato_id} em {self.data_liquidacao}"


class LiquidacaoContratoAnexo(BaseModel):
    liquidacao = models.ForeignKey(
        "tesouraria.LiquidacaoContrato",
        on_delete=models.CASCADE,
        related_name="anexos",
    )
    arquivo = models.FileField(upload_to="liquidacoes_contrato/")
    nome_arquivo = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"Anexo liquidacao#{self.liquidacao_id}"


class LiquidacaoContratoItem(BaseModel):
    liquidacao = models.ForeignKey(
        "tesouraria.LiquidacaoContrato",
        on_delete=models.CASCADE,
        related_name="itens",
    )
    parcela = models.ForeignKey(
        "contratos.Parcela",
        on_delete=models.PROTECT,
        related_name="liquidacao_itens",
    )
    numero_parcela = models.PositiveSmallIntegerField()
    referencia_mes = models.DateField()
    status_anterior = models.CharField(max_length=20)
    data_pagamento_anterior = models.DateField(null=True, blank=True)
    observacao_anterior = models.TextField(blank=True)
    valor = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["referencia_mes", "numero_parcela", "id"]

    def __str__(self) -> str:
        return (
            f"Liquidacao#{self.liquidacao_id} Parcela#{self.parcela_id} "
            f"{self.referencia_mes}"
        )


class DevolucaoAssociado(BaseModel):
    class Tipo(models.TextChoices):
        PAGAMENTO_INDEVIDO = "pagamento_indevido", "Pagamento indevido"
        DESCONTO_INDEVIDO = "desconto_indevido", "Desconto indevido"
        DESISTENCIA_POS_LIQUIDACAO = (
            "desistencia_pos_liquidacao",
            "Desistência pós-liquidação",
        )

    contrato = models.ForeignKey(
        "contratos.Contrato",
        on_delete=models.PROTECT,
        related_name="devolucoes_associado",
    )
    associado = models.ForeignKey(
        "associados.Associado",
        on_delete=models.PROTECT,
        related_name="devolucoes_associado",
    )
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    data_devolucao = models.DateField()
    quantidade_parcelas = models.PositiveSmallIntegerField(default=1)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    motivo = models.TextField()
    comprovante = models.FileField(upload_to="devolucoes_associado/")
    nome_comprovante = models.CharField(max_length=255, blank=True)
    competencia_referencia = models.DateField(null=True, blank=True)
    nome_snapshot = models.CharField(max_length=255)
    cpf_cnpj_snapshot = models.CharField(max_length=20)
    matricula_snapshot = models.CharField(max_length=60, blank=True)
    agente_snapshot = models.CharField(max_length=255, blank=True)
    contrato_codigo_snapshot = models.CharField(max_length=80)
    realizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="devolucoes_associado_realizadas",
    )
    revertida_em = models.DateTimeField(null=True, blank=True)
    revertida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="devolucoes_associado_revertidas",
    )
    motivo_reversao = models.TextField(blank=True)

    class Meta:
        ordering = ["-data_devolucao", "-created_at", "-id"]

    @property
    def status(self) -> str:
        return "revertida" if self.revertida_em else "registrada"

    def __str__(self) -> str:
        return f"Devolucao contrato#{self.contrato_id} em {self.data_devolucao}"


class DevolucaoAssociadoAnexo(BaseModel):
    devolucao = models.ForeignKey(
        "tesouraria.DevolucaoAssociado",
        on_delete=models.CASCADE,
        related_name="anexos",
    )
    arquivo = models.FileField(upload_to="devolucoes_associado/")
    nome_arquivo = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"Anexo devolucao#{self.devolucao_id}"


class Confirmacao(BaseModel):
    class Tipo(models.TextChoices):
        LIGACAO = "ligacao", "Ligação"
        AVERBACAO = "averbacao", "Averbação"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        CONFIRMADO = "confirmado", "Confirmado"
        REJEITADO = "rejeitado", "Rejeitado"

    contrato = models.ForeignKey(
        "contratos.Contrato", on_delete=models.CASCADE, related_name="confirmacoes"
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    competencia = models.DateField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDENTE
    )
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="confirmacoes_realizadas",
    )
    data_confirmacao = models.DateTimeField(null=True, blank=True)
    link_chamada = models.URLField(blank=True)
    observacao = models.TextField(blank=True)

    class Meta:
        ordering = ["contrato_id", "competencia", "tipo"]

    def confirmar(self, user, observacao: str = ""):
        self.status = self.Status.CONFIRMADO
        self.confirmado_por = user
        self.data_confirmacao = timezone.now()
        if observacao:
            self.observacao = observacao
        self.save(
            update_fields=[
                "status",
                "confirmado_por",
                "data_confirmacao",
                "observacao",
                "updated_at",
            ]
        )

    def __str__(self) -> str:
        return f"{self.contrato.codigo} - {self.tipo}"


class Pagamento(BaseModel):
    """Pagamento realizado ao associado/agente pela tesouraria (tesouraria_pagamentos)."""

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        PAGO = "pago", "Pago"
        CANCELADO = "cancelado", "Cancelado"

    class Origem(models.TextChoices):
        OPERACIONAL = "operacional", "Operacional"
        LEGADO = "legado", "Legado"
        OVERRIDE_MANUAL = "override_manual", "Override manual"

    cadastro = models.ForeignKey(
        "associados.Associado",
        on_delete=models.PROTECT,
        related_name="tesouraria_pagamentos",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tesouraria_pagamentos_criados",
    )
    contrato_codigo = models.CharField(max_length=80, blank=True)
    contrato_valor_antecipacao = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    contrato_margem_disponivel = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    cpf_cnpj = models.CharField(max_length=20)
    full_name = models.CharField(max_length=200)
    agente_responsavel = models.CharField(max_length=160, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PAGO
    )
    valor_pago = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    forma_pagamento = models.CharField(max_length=40, blank=True)
    legacy_tesouraria_pagamento_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
    )
    origem = models.CharField(
        max_length=20,
        choices=Origem.choices,
        default=Origem.OPERACIONAL,
    )
    referencias_externas = models.JSONField(default=dict, blank=True)
    comprovante_path = models.CharField(max_length=500, blank=True)
    comprovante_associado_path = models.CharField(max_length=500, blank=True)
    comprovante_agente_path = models.CharField(max_length=500, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        agente_id = getattr(self.cadastro, "agente_responsavel_id", None)
        if self.deleted_at is None and self.status == self.Status.PAGO and agente_id:
            notificacao, _ = PagamentoNotificacao.all_objects.get_or_create(
                pagamento=self,
                agente_id=agente_id,
            )
            if notificacao.deleted_at is not None:
                notificacao.restore()

    def __str__(self) -> str:
        return f"Pagamento #{self.pk} - {self.full_name} - {self.status}"


class PagamentoNotificacao(BaseModel):
    pagamento = models.ForeignKey(
        "tesouraria.Pagamento",
        on_delete=models.CASCADE,
        related_name="notificacoes",
    )
    agente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pagamento_notificacoes",
    )
    lida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["pagamento", "agente"],
                name="uniq_pagamento_notificacao_por_agente",
            )
        ]

    def __str__(self) -> str:
        return f"Notificacao pagamento#{self.pagamento_id} para agente#{self.agente_id}"
