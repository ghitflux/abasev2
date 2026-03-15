from __future__ import annotations

from rest_framework import serializers

from apps.associados.serializers import SimpleUserSerializer

from .models import Comprovante, Refinanciamento
from .payment_rules import REFINANCIAMENTO_MENSALIDADES_NECESSARIAS


class ComprovanteResumoSerializer(serializers.ModelSerializer):
    enviado_por = SimpleUserSerializer(read_only=True)

    class Meta:
        model = Comprovante
        fields = [
            "id",
            "tipo",
            "papel",
            "arquivo",
            "nome_original",
            "enviado_por",
            "created_at",
        ]


class RefinanciamentoListSerializer(serializers.ModelSerializer):
    contrato_id = serializers.IntegerField(source="contrato_origem.id", read_only=True)
    contrato_codigo = serializers.CharField(
        source="contrato_origem.codigo", read_only=True
    )
    associado_id = serializers.IntegerField(source="associado.id", read_only=True)
    associado_nome = serializers.CharField(
        source="associado.nome_completo", read_only=True
    )
    cpf_cnpj = serializers.CharField(source="associado.cpf_cnpj", read_only=True)
    agente = SimpleUserSerializer(source="contrato_origem.agente", read_only=True)
    solicitado_por = SimpleUserSerializer(read_only=True)
    aprovado_por = SimpleUserSerializer(read_only=True)
    bloqueado_por = SimpleUserSerializer(read_only=True)
    efetivado_por = SimpleUserSerializer(read_only=True)
    comprovantes = ComprovanteResumoSerializer(many=True, read_only=True)
    ciclo_key = serializers.SerializerMethodField()
    referencias = serializers.SerializerMethodField()
    itens = serializers.SerializerMethodField()
    mensalidades_pagas = serializers.SerializerMethodField()
    mensalidades_total = serializers.SerializerMethodField()
    refinanciamento_numero = serializers.SerializerMethodField()
    auditoria = serializers.SerializerMethodField()
    pagamento_status = serializers.SerializerMethodField()

    class Meta:
        model = Refinanciamento
        fields = [
            "id",
            "contrato_id",
            "contrato_codigo",
            "associado_id",
            "associado_nome",
            "cpf_cnpj",
            "agente",
            "solicitado_por",
            "aprovado_por",
            "bloqueado_por",
            "efetivado_por",
            "competencia_solicitada",
            "status",
            "valor_refinanciamento",
            "repasse_agente",
            "ciclo_key",
            "referencias",
            "itens",
            "mensalidades_pagas",
            "mensalidades_total",
            "refinanciamento_numero",
            "pagamento_status",
            "motivo_bloqueio",
            "observacao",
            "executado_em",
            "created_at",
            "updated_at",
            "auditoria",
            "comprovantes",
        ]

    def _itens_refinanciamento(self, obj: Refinanciamento):
        prefetched = getattr(obj, "_prefetched_objects_cache", {})
        itens = list(prefetched.get("itens", []))
        if itens:
            return sorted(itens, key=lambda item: (item.referencia_month, item.id))
        return list(obj.itens.all().order_by("referencia_month", "id"))

    def get_ciclo_key(self, obj: Refinanciamento) -> str:
        if obj.cycle_key:
            return obj.cycle_key
        referencias = [
            item.referencia_month.strftime("%Y-%m")
            for item in self._itens_refinanciamento(obj)
        ]
        return "|".join(referencias)

    def get_referencias(self, obj: Refinanciamento) -> list[str]:
        itens = self._itens_refinanciamento(obj)
        if itens:
            return [item.referencia_month.isoformat() for item in itens]
        return [
            referencia.isoformat()
            for referencia in [obj.ref1, obj.ref2, obj.ref3]
            if referencia is not None
        ]

    def get_itens(self, obj: Refinanciamento) -> list[dict[str, object]]:
        return [
            {
                "id": item.id,
                "numero": indice,
                "pagamento_mensalidade_id": item.pagamento_mensalidade_id,
                "referencia_mes": item.referencia_month,
                "valor": item.valor,
                "status": item.status_code or "1",
            }
            for indice, item in enumerate(self._itens_refinanciamento(obj), start=1)
        ]

    def get_mensalidades_pagas(self, obj: Refinanciamento) -> int:
        itens = self._itens_refinanciamento(obj)
        if itens:
            return min(len(itens), REFINANCIAMENTO_MENSALIDADES_NECESSARIAS)
        return min(obj.parcelas_ok, REFINANCIAMENTO_MENSALIDADES_NECESSARIAS)

    def get_mensalidades_total(self, obj: Refinanciamento) -> int:
        return REFINANCIAMENTO_MENSALIDADES_NECESSARIAS

    def get_refinanciamento_numero(self, obj: Refinanciamento) -> int:
        return (
            obj.associado.refinanciamentos.filter(created_at__lte=obj.created_at).count()
        )

    def get_auditoria(self, obj: Refinanciamento) -> dict[str, object]:
        return {
            "solicitado_por": SimpleUserSerializer(obj.solicitado_por).data
            if obj.solicitado_por
            else None,
            "aprovado_por": SimpleUserSerializer(obj.aprovado_por).data
            if obj.aprovado_por
            else None,
            "bloqueado_por": SimpleUserSerializer(obj.bloqueado_por).data
            if obj.bloqueado_por
            else None,
            "efetivado_por": SimpleUserSerializer(obj.efetivado_por).data
            if obj.efetivado_por
            else None,
            "observacao": obj.observacao,
            "motivo_bloqueio": obj.motivo_bloqueio,
        }

    def get_pagamento_status(self, obj: Refinanciamento) -> str:
        return "efetivado" if obj.status == Refinanciamento.Status.EFETIVADO else "pendente"


class RefinanciamentoDetailSerializer(RefinanciamentoListSerializer):
    pass


class BloquearRefinanciamentoSerializer(serializers.Serializer):
    motivo = serializers.CharField()


class EfetivarRefinanciamentoSerializer(serializers.Serializer):
    comprovante_associado = serializers.FileField(required=True)
    comprovante_agente = serializers.FileField(required=True)


class ElegibilidadeRefinanciamentoSerializer(serializers.Serializer):
    elegivel = serializers.BooleanField()
    motivo = serializers.CharField()
    parcelas_pagas = serializers.IntegerField()
    mensalidades_livres = serializers.IntegerField()
    tem_refinanciamento_ativo = serializers.BooleanField()
