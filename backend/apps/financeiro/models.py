from django.conf import settings
from django.db import models

from core.models import BaseModel


class Despesa(BaseModel):
    """Despesa operacional do sistema (despesas)."""

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        PAGO = "pago", "Pago"

    class Tipo(models.TextChoices):
        FIXA = "fixa", "Fixa"
        VARIAVEL = "variavel", "Variável"

    class StatusAnexo(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        ANEXADO = "anexado", "Anexado"

    class Recorrencia(models.TextChoices):
        NENHUMA = "nenhuma", "Nenhuma"
        MENSAL = "mensal", "Mensal"
        TRIMESTRAL = "trimestral", "Trimestral"
        ANUAL = "anual", "Anual"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="despesas",
    )
    categoria = models.CharField(max_length=100)
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=15, decimal_places=2)
    data_despesa = models.DateField()
    data_pagamento = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDENTE
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices, blank=True)
    recorrencia = models.CharField(
        max_length=20, choices=Recorrencia.choices, default=Recorrencia.NENHUMA
    )
    recorrencia_ativa = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True)
    anexo = models.FileField(upload_to="despesas/", null=True, blank=True)
    nome_anexo = models.CharField(max_length=255, blank=True)
    status_anexo = models.CharField(
        max_length=20,
        choices=StatusAnexo.choices,
        default=StatusAnexo.PENDENTE,
    )
    comprovantes_json = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-data_despesa"]

    def __str__(self) -> str:
        return f"{self.categoria} - {self.descricao} (R$ {self.valor})"
