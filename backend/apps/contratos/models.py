from __future__ import annotations

import secrets
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import BaseModel


class Contrato(BaseModel):
    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        EM_ANALISE = "em_analise", "Em análise"
        ATIVO = "ativo", "Ativo"
        ENCERRADO = "encerrado", "Encerrado"
        CANCELADO = "cancelado", "Cancelado"

    associado = models.ForeignKey(
        "associados.Associado", on_delete=models.PROTECT, related_name="contratos"
    )
    agente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="contratos_agenciados",
        null=True,
        blank=True,
    )
    codigo = models.CharField(max_length=40, unique=True, blank=True)
    valor_bruto = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_liquido = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_mensalidade = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    prazo_meses = models.PositiveSmallIntegerField(default=3)
    taxa_antecipacao = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    margem_disponivel = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    valor_total_antecipacao = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    doacao_associado = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    comissao_agente = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.EM_ANALISE
    )
    data_contrato = models.DateField(default=timezone.now)
    data_aprovacao = models.DateField(null=True, blank=True)
    data_primeira_mensalidade = models.DateField(null=True, blank=True)
    mes_averbacao = models.DateField(null=True, blank=True)
    contato_web = models.BooleanField(default=False)
    termos_web = models.BooleanField(default=False)
    auxilio_liberado_em = models.DateField(null=True, blank=True)
    comprovante_pix = models.FileField(
        upload_to="comprovantes_pix/", null=True, blank=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.codigo or "Contrato sem código"

    def save(self, *args, **kwargs):
        def to_decimal(value):
            if value in (None, ""):
                return None
            if isinstance(value, Decimal):
                return value
            try:
                return Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError):
                return None

        if not self.codigo:
            timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
            self.codigo = f"CTR-{timestamp}-{secrets.token_hex(3).upper()}"
        base_comissao = to_decimal(self.valor_mensalidade) or to_decimal(self.valor_bruto)
        if base_comissao:
            self.comissao_agente = (base_comissao * Decimal("0.10")).quantize(
                Decimal("0.01")
            )
        valor_mensalidade = to_decimal(self.valor_mensalidade)
        if valor_mensalidade and self.prazo_meses:
            self.valor_total_antecipacao = (
                valor_mensalidade * self.prazo_meses
            ).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)


class Ciclo(BaseModel):
    class Status(models.TextChoices):
        FUTURO = "futuro", "Futuro"
        ABERTO = "aberto", "Aberto"
        CICLO_RENOVADO = "ciclo_renovado", "Ciclo renovado"
        APTO_A_RENOVAR = "apto_a_renovar", "Apto a renovar"
        FECHADO = "fechado", "Fechado"

    contrato = models.ForeignKey(
        Contrato, on_delete=models.CASCADE, related_name="ciclos"
    )
    numero = models.PositiveSmallIntegerField(default=1)
    data_inicio = models.DateField()
    data_fim = models.DateField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.FUTURO
    )
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ("contrato", "numero")
        ordering = ["contrato_id", "numero"]

    def __str__(self) -> str:
        return f"{self.contrato.codigo} - ciclo {self.numero}"


class Parcela(BaseModel):
    class Status(models.TextChoices):
        FUTURO = "futuro", "Futuro"
        EM_ABERTO = "em_aberto", "Em aberto"
        DESCONTADO = "descontado", "Descontado"
        NAO_DESCONTADO = "nao_descontado", "Não descontado"
        CANCELADO = "cancelado", "Cancelado"

    ciclo = models.ForeignKey(Ciclo, on_delete=models.CASCADE, related_name="parcelas")
    numero = models.PositiveSmallIntegerField()
    referencia_mes = models.DateField()
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data_vencimento = models.DateField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.EM_ABERTO
    )
    data_pagamento = models.DateField(null=True, blank=True)
    observacao = models.TextField(blank=True)

    class Meta:
        unique_together = ("ciclo", "numero")
        ordering = ["ciclo_id", "numero"]

    def __str__(self) -> str:
        return f"{self.ciclo} - parcela {self.numero}"
