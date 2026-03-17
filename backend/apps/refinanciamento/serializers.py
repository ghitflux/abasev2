from __future__ import annotations

from rest_framework import serializers

from apps.associados.serializers import SimpleUserSerializer
from apps.contratos.cycle_timeline import (
    get_contract_first_cycle_activation_info,
    get_contract_cycle_size,
    get_refinanciamento_activation_info,
)
from core.file_references import build_filefield_reference

from .models import Comprovante, Refinanciamento


class ComprovanteResumoSerializer(serializers.ModelSerializer):
    enviado_por = SimpleUserSerializer(read_only=True)
    arquivo_referencia = serializers.SerializerMethodField()
    arquivo_disponivel_localmente = serializers.SerializerMethodField()
    tipo_referencia = serializers.SerializerMethodField()

    class Meta:
        model = Comprovante
        fields = [
            "id",
            "refinanciamento",
            "contrato",
            "ciclo",
            "tipo",
            "papel",
            "arquivo",
            "arquivo_referencia",
            "arquivo_disponivel_localmente",
            "tipo_referencia",
            "nome_original",
            "mime",
            "size_bytes",
            "data_pagamento",
            "origem",
            "legacy_comprovante_id",
            "enviado_por",
            "created_at",
        ]

    def get_arquivo_referencia(self, obj: Comprovante) -> str:
        return self._reference(obj).arquivo_referencia

    def get_arquivo_disponivel_localmente(self, obj: Comprovante) -> bool:
        return self._reference(obj).arquivo_disponivel_localmente

    def get_tipo_referencia(self, obj: Comprovante) -> str:
        return self._reference(obj).tipo_referencia

    def _reference(self, obj: Comprovante):
        request = self.context.get("request")
        reference = build_filefield_reference(
            obj.arquivo,
            request=request,
            missing_type="legado_sem_arquivo",
        )
        if obj.arquivo_referencia and obj.arquivo_referencia != reference.arquivo_referencia:
            return reference.__class__(
                url=reference.url,
                arquivo_referencia=obj.arquivo_referencia,
                arquivo_disponivel_localmente=reference.arquivo_disponivel_localmente,
                tipo_referencia=reference.tipo_referencia,
            )
        return reference


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
    data_primeiro_ciclo_ativado = serializers.SerializerMethodField()
    data_ativacao_ciclo = serializers.SerializerMethodField()
    origem_data_ativacao = serializers.SerializerMethodField()
    data_solicitacao_renovacao = serializers.SerializerMethodField()
    ativacao_inferida = serializers.SerializerMethodField()
    etapa_operacional = serializers.SerializerMethodField()
    data_renovacao = serializers.SerializerMethodField()
    origem_renovacao = serializers.SerializerMethodField()
    motivo_apto_renovacao = serializers.SerializerMethodField()
    legacy_refinanciamento_id = serializers.IntegerField(read_only=True)
    origem = serializers.CharField(read_only=True)

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
            "legacy_refinanciamento_id",
            "origem",
            "data_renovacao",
            "origem_renovacao",
            "motivo_apto_renovacao",
            "data_primeiro_ciclo_ativado",
            "data_ativacao_ciclo",
            "origem_data_ativacao",
            "data_solicitacao_renovacao",
            "ativacao_inferida",
            "etapa_operacional",
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
            for referencia in [obj.ref1, obj.ref2, obj.ref3, obj.ref4]
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
        total = self.get_mensalidades_total(obj)
        itens = self._itens_refinanciamento(obj)
        if itens:
            return min(len(itens), total)
        return min(obj.parcelas_ok, total)

    def get_mensalidades_total(self, obj: Refinanciamento) -> int:
        if obj.contrato_origem is not None:
            return get_contract_cycle_size(obj.contrato_origem)
        itens = self._itens_refinanciamento(obj)
        return max(len(itens), 3)

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
        return (
            "efetivado"
            if get_refinanciamento_activation_info(obj).activated_at is not None
            else "pendente"
        )

    def get_data_primeiro_ciclo_ativado(self, obj: Refinanciamento):
        if obj.contrato_origem is None:
            return None
        return get_contract_first_cycle_activation_info(obj.contrato_origem).activated_at

    def get_data_renovacao(self, obj: Refinanciamento):
        return obj.data_ativacao_ciclo or obj.executado_em or obj.created_at

    def get_origem_renovacao(self, obj: Refinanciamento) -> str:
        return obj.origem

    def get_data_ativacao_ciclo(self, obj: Refinanciamento):
        return get_refinanciamento_activation_info(obj).activated_at

    def get_origem_data_ativacao(self, obj: Refinanciamento) -> str:
        return get_refinanciamento_activation_info(obj).source

    def get_data_solicitacao_renovacao(self, obj: Refinanciamento):
        return obj.data_ativacao_ciclo or obj.executado_em or obj.created_at

    def get_ativacao_inferida(self, obj: Refinanciamento) -> bool:
        return get_refinanciamento_activation_info(obj).inferred

    def get_etapa_operacional(self, obj: Refinanciamento) -> str:
        return obj.status

    def get_motivo_apto_renovacao(self, obj: Refinanciamento) -> str:
        total = self.get_mensalidades_total(obj)
        pagas = min(self.get_mensalidades_pagas(obj), total)
        ciclo_numero = obj.ciclo_origem.numero if obj.ciclo_origem_id else 1
        if total > 0 and pagas == total - 1:
            return (
                f"{pagas}/{total} parcelas quitadas; última em previsão; "
                f"ciclo {ciclo_numero} elegível"
            )
        if total > 0 and pagas >= total:
            return (
                f"{pagas}/{total} parcelas quitadas; renovação em andamento; "
                f"ciclo {ciclo_numero} elegível"
            )
        return (
            f"{pagas}/{total} parcelas quitadas; "
            f"ciclo {ciclo_numero} em acompanhamento"
        )


class RefinanciamentoDetailSerializer(RefinanciamentoListSerializer):
    pass


class BloquearRefinanciamentoSerializer(serializers.Serializer):
    motivo = serializers.CharField()


class DesativarRefinanciamentoSerializer(serializers.Serializer):
    motivo = serializers.CharField()


class EfetivarRefinanciamentoSerializer(serializers.Serializer):
    comprovante_associado = serializers.FileField(required=True)
    comprovante_agente = serializers.FileField(required=True)


class AprovarAnaliseRefinanciamentoSerializer(serializers.Serializer):
    termo_antecipacao = serializers.FileField(required=True)
    observacao = serializers.CharField(required=False, allow_blank=True, default="")


class AprovarEmMassaRefinanciamentoSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    confirm_text = serializers.CharField()

    def validate_confirm_text(self, value: str) -> str:
        if value.strip().upper() != "CONFIRMAR":
            raise serializers.ValidationError(
                "Digite CONFIRMAR para executar a aprovação em massa."
            )
        return value


class ElegibilidadeRefinanciamentoSerializer(serializers.Serializer):
    elegivel = serializers.BooleanField()
    motivo = serializers.CharField()
    parcelas_pagas = serializers.IntegerField()
    mensalidades_livres = serializers.IntegerField()
    tem_refinanciamento_ativo = serializers.BooleanField()
