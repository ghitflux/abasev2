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

    def __str__(self) -> str:
        return f"Pagamento #{self.pk} - {self.full_name} - {self.status}"
