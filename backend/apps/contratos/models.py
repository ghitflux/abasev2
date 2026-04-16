from __future__ import annotations

import secrets
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import AllObjectsManager, BaseModel, SoftDeleteManager, SoftDeleteQuerySet


def build_competencia_lock(associado_id: int | None, referencia_mes) -> str | None:
    if not associado_id or not referencia_mes:
        return None
    return f"{associado_id}:{referencia_mes.strftime('%Y-%m')}"


class Contrato(BaseModel):
    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        EM_ANALISE = "em_analise", "Em análise"
        ATIVO = "ativo", "Ativo"
        ENCERRADO = "encerrado", "Encerrado"
        CANCELADO = "cancelado", "Cancelado"

    class TipoUnificacao(models.TextChoices):
        RETIMP_SHADOW = "retimp_shadow", "Contrato RETIMP sombra"
        DUPLICATE_CTR_SHADOW = "duplicate_ctr_shadow", "Contrato CTR duplicado sombra"

    class CancelamentoTipo(models.TextChoices):
        CANCELADO = "cancelado", "Cancelado"
        DESISTENTE = "desistente", "Desistente"

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
    admin_manual_layout_enabled = models.BooleanField(default=False)
    admin_manual_layout_updated_at = models.DateTimeField(null=True, blank=True)
    allow_small_value_renewal = models.BooleanField(default=False)
    cancelamento_tipo = models.CharField(
        max_length=20,
        choices=CancelamentoTipo.choices,
        blank=True,
        default="",
    )
    cancelamento_motivo = models.TextField(blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    contrato_canonico = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="contratos_sombra",
    )
    tipo_unificacao = models.CharField(
        max_length=30,
        choices=TipoUnificacao.choices,
        blank=True,
        default="",
    )
    unificado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.codigo or "Contrato sem código"

    @staticmethod
    def _to_decimal(value):
        if value in (None, ""):
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    def resolve_percentual_repasse(self) -> Decimal:
        percentual_repasse = Decimal("10.00")
        if self.associado_id and getattr(self, "associado", None):
            associado_percentual = self._to_decimal(
                getattr(self.associado, "auxilio_taxa", None)
            )
            if associado_percentual is not None:
                percentual_repasse = associado_percentual
        return percentual_repasse

    def calculate_comissao_agente(self) -> Decimal | None:
        # O repasse do agente deve seguir o valor efetivamente liberado ao associado.
        base_comissao = self._to_decimal(self.margem_disponivel)
        if base_comissao is None or base_comissao <= 0:
            base_comissao = self._to_decimal(self.valor_mensalidade) or self._to_decimal(
                self.valor_bruto
            )
        if base_comissao is None:
            return None
        percentual_repasse = self.resolve_percentual_repasse()
        return (base_comissao * (percentual_repasse / Decimal("100"))).quantize(
            Decimal("0.01")
        )

    def save(self, *args, **kwargs):
        if not self.codigo:
            timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
            self.codigo = f"CTR-{timestamp}-{secrets.token_hex(3).upper()}"
        comissao_agente = self.calculate_comissao_agente()
        if comissao_agente is not None and not self.comissao_agente:
            self.comissao_agente = comissao_agente
        valor_mensalidade = self._to_decimal(self.valor_mensalidade)
        if valor_mensalidade and self.prazo_meses:
            self.valor_total_antecipacao = (
                valor_mensalidade * self.prazo_meses
            ).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)
        if self.associado_id:
            self.associado.sync_contrato_snapshot(self)

    @property
    def is_shadow_duplicate(self) -> bool:
        return self.contrato_canonico_id is not None


class Ciclo(BaseModel):
    class Status(models.TextChoices):
        FUTURO = "futuro", "Futuro"
        ABERTO = "aberto", "Aberto"
        PENDENCIA = "pendencia", "Pendência"
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


class ParcelaQuerySet(SoftDeleteQuerySet):
    def bulk_create(self, objs, **kwargs):
        competencia_groups: set[tuple[int, object]] = set()
        for obj in objs:
            obj.sync_competencia_fields()
            if obj.associado_id and obj.referencia_mes:
                competencia_groups.add((obj.associado_id, obj.referencia_mes))
        created = super().bulk_create(objs, **kwargs)
        for associado_id, referencia_mes in competencia_groups:
            self.model.sync_group_locks(
                associado_id=associado_id,
                referencia_mes=referencia_mes,
            )
        return created


class ParcelaManager(SoftDeleteManager):
    def get_queryset(self):
        return ParcelaQuerySet(self.model, using=self._db).alive()


class ParcelaAllObjectsManager(AllObjectsManager):
    def get_queryset(self):
        return ParcelaQuerySet(self.model, using=self._db)


class Parcela(BaseModel):
    class LayoutBucket(models.TextChoices):
        CYCLE = "cycle", "No ciclo"
        UNPAID = "unpaid", "Parcelas não descontadas"
        MOVEMENT = "movement", "Movimento financeiro avulso"

    class Status(models.TextChoices):
        FUTURO = "futuro", "Futuro"
        EM_ABERTO = "em_aberto", "Em aberto"
        EM_PREVISAO = "em_previsao", "Em previsão"
        DESCONTADO = "descontado", "Descontado"
        LIQUIDADA = "liquidada", "Liquidada"
        NAO_DESCONTADO = "nao_descontado", "Não descontado"
        CANCELADO = "cancelado", "Cancelado"

    ciclo = models.ForeignKey(Ciclo, on_delete=models.CASCADE, related_name="parcelas")
    associado = models.ForeignKey(
        "associados.Associado",
        on_delete=models.PROTECT,
        related_name="parcelas",
    )
    numero = models.PositiveSmallIntegerField()
    referencia_mes = models.DateField()
    competencia_lock = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        unique=True,
    )
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data_vencimento = models.DateField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.EM_ABERTO
    )
    layout_bucket = models.CharField(
        max_length=20,
        choices=LayoutBucket.choices,
        default=LayoutBucket.CYCLE,
    )
    data_pagamento = models.DateField(null=True, blank=True)
    observacao = models.TextField(blank=True)
    descartado_em = models.DateTimeField(null=True, blank=True)
    descartado_por = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="parcelas_descartadas",
    )

    objects = ParcelaManager()
    all_objects = ParcelaAllObjectsManager()

    class Meta:
        unique_together = ("ciclo", "numero")
        ordering = ["ciclo_id", "numero"]
        indexes = [
            models.Index(fields=["associado", "referencia_mes"]),
        ]

    def __str__(self) -> str:
        return f"{self.ciclo} - parcela {self.numero}"

    @classmethod
    def sync_group_locks(cls, *, associado_id: int | None, referencia_mes) -> None:
        if not associado_id or not referencia_mes:
            return
        queryset = cls.all_objects.filter(
            associado_id=associado_id,
            referencia_mes=referencia_mes,
            deleted_at__isnull=True,
        ).exclude(status=cls.Status.CANCELADO)
        active_ids = list(queryset.values_list("id", flat=True))
        if not active_ids:
            return
        if len(active_ids) == 1:
            cls.all_objects.filter(pk=active_ids[0]).update(
                competencia_lock=build_competencia_lock(associado_id, referencia_mes)
            )
            return
        cls.all_objects.filter(pk__in=active_ids).update(competencia_lock=None)

    def sync_competencia_fields(self):
        if not self.associado_id and self.ciclo_id:
            ciclo = getattr(self, "ciclo", None)
            if ciclo and getattr(ciclo, "contrato_id", None):
                self.associado_id = ciclo.contrato.associado_id
            else:
                self.associado_id = (
                    Ciclo.objects.select_related("contrato")
                    .only("contrato__associado_id")
                    .get(pk=self.ciclo_id)
                    .contrato.associado_id
                )

        if self.deleted_at is not None or self.status == self.Status.CANCELADO:
            self.competencia_lock = None
        else:
            siblings = type(self).all_objects.filter(
                associado_id=self.associado_id,
                referencia_mes=self.referencia_mes,
                deleted_at__isnull=True,
            ).exclude(status=self.Status.CANCELADO)
            if self.pk:
                siblings = siblings.exclude(pk=self.pk)
            self.competencia_lock = (
                None
                if siblings.exists()
                else build_competencia_lock(
                    self.associado_id,
                    self.referencia_mes,
                )
            )

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        previous_group = None
        if self.pk:
            previous_group = (
                type(self)
                .all_objects.filter(pk=self.pk)
                .values_list("associado_id", "referencia_mes")
                .first()
            )
        self.sync_competencia_fields()
        if update_fields is not None:
            merged_fields = set(update_fields)
            merged_fields.update({"associado", "competencia_lock"})
            kwargs["update_fields"] = list(merged_fields)
        super().save(*args, **kwargs)
        type(self).sync_group_locks(
            associado_id=self.associado_id,
            referencia_mes=self.referencia_mes,
        )
        if previous_group and previous_group != (self.associado_id, self.referencia_mes):
            type(self).sync_group_locks(
                associado_id=previous_group[0],
                referencia_mes=previous_group[1],
            )
