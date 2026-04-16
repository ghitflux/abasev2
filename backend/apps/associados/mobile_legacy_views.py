from __future__ import annotations

import json
import logging
from datetime import datetime

from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import permissions, serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.legacy_helpers import map_estado_civil
from apps.accounts.mobile_legacy_auth import (
    LegacyMobileTokenAuthentication,
    ensure_associado_user,
    only_digits,
)
from apps.accounts.mobile_maintenance import MobileMaintenanceMixin
from apps.contratos.canonicalization import resolve_operational_contract_for_associado
from apps.contratos.models import Contrato
from apps.esteira.models import DocIssue, DocReupload
from apps.esteira.services import EsteiraService

from .mobile_legacy import (
    build_antecipacao_payload,
    build_auxilio2_payload,
    build_bootstrap_payload,
    build_cadastro_payload,
    build_issues_payload,
    build_mensalidades_payload,
    build_pessoa_payload,
    build_status_payload,
    build_termo_adesao_payload,
    build_vinculo_publico_payload,
    create_auxilio2_charge,
    resolve_mobile_associado,
)
from .models import Associado, Documento

logger = logging.getLogger(__name__)

DOCUMENT_UPLOAD_FIELDS = {
    "cpf_frente": Documento.Tipo.DOCUMENTO_FRENTE,
    "cpf_verso": Documento.Tipo.DOCUMENTO_VERSO,
    "comp_endereco": Documento.Tipo.COMPROVANTE_RESIDENCIA,
    "contracheque_atual": Documento.Tipo.CONTRACHEQUE,
    "termo_adesao": Documento.Tipo.TERMO_ADESAO,
    "termo_antecipacao": Documento.Tipo.TERMO_ANTECIPACAO,
}
MARITAL_STATUS_MAP = {
    "SOLTEIRO": "solteiro",
    "CASADO": "casado",
    "SEPARADO": "divorciado",
    "DIVORCIADO": "divorciado",
    "VIUVO": "viuvo",
    "UNIAO_ESTAVEL": "uniao_estavel",
}


class LegacyNoopSerializer(serializers.Serializer):
    pass


class LegacyMobileAPIView(MobileMaintenanceMixin, APIView):
    authentication_classes = [LegacyMobileTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LegacyNoopSerializer


def parse_date(value: str | None):
    if value in (None, ""):
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _merged_payload(data) -> dict[str, object]:
    payload = {}
    raw_payload = data.get("payload")
    if raw_payload:
        try:
            parsed = json.loads(raw_payload)
            if isinstance(parsed, dict):
                payload.update(parsed)
        except json.JSONDecodeError:
            pass

    for key, value in data.items():
        if key == "payload":
            continue
        payload[key] = value
    return payload


def _normalized_marital_status(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    mapped = MARITAL_STATUS_MAP.get(raw.upper())
    if mapped:
        return mapped
    return map_estado_civil(raw)


def _normalized_tipo_conta(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"corrente", "poupanca", "salario"}:
        return normalized
    return ""


def _payload_text(payload: dict[str, object], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _candidate_email_for_user(user, payload_email: str | None) -> str | None:
    payload_email = (payload_email or "").strip().lower()
    if not payload_email:
        return None
    if user.email and not user.email.endswith("@app.abase.local"):
        return None
    from apps.accounts.models import User  # noqa: PLC0415

    if User.all_objects.filter(email__iexact=payload_email).exclude(pk=user.pk).exists():
        return None
    return payload_email


def _resolve_or_create_associado(user, payload: dict[str, object]) -> Associado:
    cpf = only_digits(str(payload.get("cpf_cnpj") or ""))
    if not cpf:
        raise serializers.ValidationError({"cpf_cnpj": "Informe o CPF/CNPJ do cadastro."})

    current = resolve_mobile_associado(user)
    target = current

    duplicate = Associado.all_objects.filter(cpf_cnpj=cpf).exclude(
        pk=current.pk if current else None
    ).first()
    if duplicate and duplicate.user_id not in {None, user.pk}:
        raise serializers.ValidationError(
            {"cpf_cnpj": "Este CPF já está vinculado a outro cadastro."}
        )

    if target is None:
        target = duplicate or Associado(user=user, cpf_cnpj=cpf)
    elif duplicate and duplicate.pk != target.pk:
        target = duplicate

    target.user = user
    target.cpf_cnpj = cpf
    target.tipo_documento = (
        Associado.TipoDocumento.CNPJ if str(payload.get("doc_type") or "").upper() == "CNPJ" else Associado.TipoDocumento.CPF
    )
    target.nome_completo = str(payload.get("full_name") or target.nome_completo or user.full_name or "Associado")[:255]
    target.rg = str(payload.get("rg") or target.rg or "")[:30]
    target.orgao_expedidor = str(payload.get("orgao_expedidor") or target.orgao_expedidor or "")[:80]
    target.data_nascimento = parse_date(payload.get("birth_date"))
    target.profissao = _payload_text(payload, "profissao", "profession", "cargo", "job_title")[:120] or target.profissao or ""
    target.cargo = _payload_text(payload, "cargo", "profession", "profissao")[:120] or target.cargo or ""
    target.estado_civil = _normalized_marital_status(
        _payload_text(payload, "estado_civil", "marital_status", "maritalStatus")
        or target.estado_civil
        or ""
    )
    target.cep = str(payload.get("cep") or target.cep or "")[:12]
    target.logradouro = _payload_text(payload, "logradouro", "address")[:255] or target.logradouro or ""
    target.numero = _payload_text(payload, "numero", "address_number", "addressNumber")[:60] or target.numero or ""
    target.complemento = _payload_text(payload, "complemento", "complement")[:120] or target.complemento or ""
    target.bairro = _payload_text(payload, "bairro", "neighborhood")[:120] or target.bairro or ""
    target.cidade = _payload_text(payload, "cidade", "city")[:120] or target.cidade or ""
    target.uf = str(payload.get("uf") or target.uf or "").upper()[:2]
    target.telefone = str(payload.get("cellphone") or target.telefone or "")[:30]
    target.orgao_publico = str(payload.get("orgao_publico") or target.orgao_publico or "")[:160]
    target.situacao_servidor = str(payload.get("situacao_servidor") or target.situacao_servidor or "")[:80]
    target.matricula_orgao = _payload_text(
        payload,
        "matricula_orgao",
        "matricula_servidor_publico",
        "matriculaServidorPublico",
    )[:60] or target.matricula_orgao or ""
    target.email = str(payload.get("email") or target.email or user.email or "")[:254]
    target.banco = _payload_text(payload, "banco", "bank_name")[:100] or target.banco or ""
    target.agencia = _payload_text(payload, "agencia", "bank_agency")[:20] or target.agencia or ""
    target.conta = _payload_text(payload, "conta", "bank_account")[:30] or target.conta or ""
    target.tipo_conta = _normalized_tipo_conta(
        _payload_text(payload, "tipo_conta", "account_type") or target.tipo_conta or ""
    )
    target.chave_pix = _payload_text(payload, "chave_pix", "pix_key")[:120] or target.chave_pix or ""
    if not target.auxilio1_status:
        target.auxilio1_status = "bloqueado"
    if not target.auxilio2_status:
        target.auxilio2_status = "bloqueado"
    if not target.status or target.status == Associado.Status.CADASTRADO:
        target.status = Associado.Status.EM_ANALISE
    target.save()

    if candidate_email := _candidate_email_for_user(user, target.email):
        user.email = candidate_email
        user.save(update_fields=["email", "updated_at"])

    ensure_associado_user(target)
    EsteiraService.garantir_item_inicial_cadastro(target, user)
    return target


def _upsert_documento(*, associado: Associado, tipo: str, upload, observacao: str = "") -> Documento:
    documento = Documento.objects.filter(associado=associado, tipo=tipo).first()
    if documento is None:
        documento = Documento.objects.create(
            associado=associado,
            tipo=tipo,
            arquivo=upload,
            origem=Documento.Origem.OUTRO,
            status=Documento.Status.PENDENTE,
            observacao=observacao,
        )
        return documento

    documento.arquivo = upload
    documento.origem = Documento.Origem.OUTRO
    documento.status = Documento.Status.PENDENTE
    documento.observacao = observacao
    documento.save(update_fields=["arquivo", "origem", "status", "observacao", "updated_at"])
    return documento


class LegacyAssociadoMeView(LegacyMobileAPIView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        associado = resolve_mobile_associado(request.user)
        return Response(
            {
                "ok": True,
                "pessoa": build_pessoa_payload(associado),
                "vinculo_publico": build_vinculo_publico_payload(associado),
                "cadastro": build_cadastro_payload(associado, request=request),
            },
            status=status.HTTP_200_OK,
        )


class LegacyAssociadoA2StatusView(LegacyMobileAPIView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        associado = resolve_mobile_associado(request.user)
        return Response(build_status_payload(associado, request=request), status=status.HTTP_200_OK)


class LegacyAssociadoTermoAdesaoView(LegacyMobileAPIView):
    @extend_schema(responses={302: OpenApiTypes.URI})
    def get(self, request):
        associado = resolve_mobile_associado(request.user)
        payload = build_termo_adesao_payload(associado, request=request)
        if payload is None or not payload.get("url"):
            raise Http404("Termo de adesão não encontrado.")
        return HttpResponseRedirect(payload["url"])


class LegacyMensalidadesView(LegacyMobileAPIView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        associado = resolve_mobile_associado(request.user)
        return Response(
            build_mensalidades_payload(
                associado,
                ref_from=request.query_params.get("ref_from"),
                ref_to=request.query_params.get("ref_to"),
            ),
            status=status.HTTP_200_OK,
        )


class LegacyAntecipacaoHistoricoView(LegacyMobileAPIView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        associado = resolve_mobile_associado(request.user)
        return Response(build_antecipacao_payload(associado), status=status.HTTP_200_OK)


class LegacyClientLogView(LegacyMobileAPIView):
    @extend_schema(
        request=OpenApiTypes.OBJECT,
        responses={
            200: inline_serializer(
                name="LegacyClientLogResponse",
                fields={"ok": serializers.BooleanField()},
            )
        },
    )
    def post(self, request):
        logger.info(
            "mobile-client-log",
            extra={
                "user_id": request.user.id,
                "payload": request.data,
            },
        )
        return Response({"ok": True}, status=status.HTTP_200_OK)


class LegacyAssociadoDoisStatusView(LegacyMobileAPIView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        associado = resolve_mobile_associado(request.user)
        return Response(build_status_payload(associado, request=request), status=status.HTTP_200_OK)


class LegacyAssociadoDoisCadastroView(LegacyMobileAPIView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        associado = resolve_mobile_associado(request.user)
        return Response(
            {
                "exists": associado is not None,
                "cadastro": build_cadastro_payload(associado, request=request),
            },
            status=status.HTTP_200_OK,
        )


class LegacyAssociadoDoisCheckCpfView(LegacyMobileAPIView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        cpf = only_digits(request.query_params.get("cpf"))
        if not cpf:
            return Response(
                {"exists": False},
                status=status.HTTP_200_OK,
            )

        associado = resolve_mobile_associado(request.user)
        duplicate = Associado.all_objects.filter(cpf_cnpj=cpf).exclude(
            pk=associado.pk if associado else None
        ).first()
        return Response(
            {
                "exists": duplicate is not None,
                "data": None
                if duplicate is None
                else {
                    "full_name": duplicate.nome_completo,
                },
            },
            status=status.HTTP_200_OK,
        )


class LegacyAssociadoDoisAtualizarBasicoView(LegacyMobileAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(request=OpenApiTypes.OBJECT, responses={200: OpenApiTypes.OBJECT})
    @transaction.atomic
    def post(self, request):
        payload = _merged_payload(request.data)
        associado = _resolve_or_create_associado(request.user, payload)

        for field_name, document_type in DOCUMENT_UPLOAD_FIELDS.items():
            upload = request.FILES.get(field_name)
            if upload is None:
                continue
            _upsert_documento(
                associado=associado,
                tipo=document_type,
                upload=upload,
                observacao="Documento enviado no fluxo mobile.",
            )

        return Response(
            {
                "ok": True,
                "message": "Cadastro atualizado com sucesso.",
                "cadastro": build_cadastro_payload(associado, request=request),
            },
            status=status.HTTP_200_OK,
        )


class LegacyAssociadoDoisIssuesView(LegacyMobileAPIView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        associado = resolve_mobile_associado(request.user)
        return Response(build_issues_payload(associado), status=status.HTTP_200_OK)


class LegacyAssociadoDoisReuploadsView(LegacyMobileAPIView):
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(request=OpenApiTypes.OBJECT, responses={200: OpenApiTypes.OBJECT})
    @transaction.atomic
    def post(self, request):
        associado = resolve_mobile_associado(request.user)
        if associado is None:
            return Response(
                {"ok": False, "message": "Cadastre seus dados antes de reenviar documentos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        issue_id = request.data.get("associadodois_doc_issue_id")
        issue = None
        if issue_id:
            issue = DocIssue.objects.filter(pk=issue_id, associado=associado).first()
            if issue is None:
                return Response(
                    {"ok": False, "message": "Pendência documental não encontrada."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        saved_count = 0
        notes = str(request.data.get("notes") or "")
        extras_raw = request.data.get("extras")
        try:
            extras = json.loads(extras_raw) if extras_raw else None
        except json.JSONDecodeError:
            extras = None

        uploads_snapshot = list(issue.agent_uploads_json or []) if issue else []

        for field_name, document_type in DOCUMENT_UPLOAD_FIELDS.items():
            upload = request.FILES.get(field_name)
            if upload is None:
                continue

            documento = _upsert_documento(
                associado=associado,
                tipo=document_type,
                upload=upload,
                observacao=notes or "Reenvio de documento pelo aplicativo.",
            )
            saved_count += 1

            if issue is not None:
                DocReupload.objects.create(
                    doc_issue=issue,
                    associado=associado,
                    uploaded_by=request.user,
                    cpf_cnpj=associado.cpf_cnpj,
                    contrato_codigo=associado.contrato_codigo_contrato or "",
                    file_original_name=upload.name,
                    file_stored_name=documento.arquivo.name.split("/")[-1],
                    file_relative_path=documento.arquivo.name,
                    file_mime=getattr(upload, "content_type", "") or "",
                    file_size_bytes=getattr(upload, "size", None),
                    status=DocReupload.Status.RECEBIDO,
                    uploaded_at=timezone.now(),
                    notes=notes,
                    extras=extras,
                )
                uploads_snapshot.append(
                    {
                        "field": field_name,
                        "file_relative_path": documento.arquivo.name,
                        "uploaded_at": timezone.now().isoformat(),
                        "notes": notes,
                    }
                )

        if saved_count == 0:
            return Response(
                {"ok": False, "message": "Nenhum arquivo foi enviado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if issue is not None:
            issue.agent_uploads_json = uploads_snapshot
            issue.save(update_fields=["agent_uploads_json", "updated_at"])

        return Response(
            {
                "ok": True,
                "message": "Arquivos recebidos com sucesso.",
                "saved_count": saved_count,
            },
            status=status.HTTP_200_OK,
        )


class LegacyAssociadoDoisAceiteTermosView(LegacyMobileAPIView):
    @extend_schema(
        responses={
            200: inline_serializer(
                name="LegacyAceiteTermosResponse",
                fields={
                    "ok": serializers.BooleanField(),
                    "aceite_termos": serializers.BooleanField(),
                },
            )
        }
    )
    @transaction.atomic
    def post(self, request):
        associado = resolve_mobile_associado(request.user)
        if associado is None:
            return Response(
                {"ok": False, "message": "Cadastre seus dados antes de aceitar os termos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        associado.aceite_termos = True
        associado.save(update_fields=["aceite_termos", "updated_at"])
        contrato = resolve_operational_contract_for_associado(associado)
        if contrato is not None:
            contrato.termos_web = True
            contrato.save(update_fields=["termos_web", "updated_at"])

        return Response({"ok": True, "aceite_termos": True}, status=status.HTTP_200_OK)


class LegacyAssociadoDoisContatoView(LegacyMobileAPIView):
    @extend_schema(
        responses={
            200: inline_serializer(
                name="LegacyContatoResponse",
                fields={
                    "ok": serializers.BooleanField(),
                    "contato_status": serializers.CharField(),
                },
            )
        }
    )
    @transaction.atomic
    def post(self, request):
        associado = resolve_mobile_associado(request.user)
        if associado is None:
            return Response(
                {"ok": False, "message": "Cadastre seus dados antes de solicitar contato."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        associado.contato_status = "solicitado"
        associado.contato_updated_at = timezone.now()
        associado.save(update_fields=["contato_status", "contato_updated_at", "updated_at"])
        contrato = resolve_operational_contract_for_associado(associado)
        if contrato is not None:
            contrato.contato_web = True
            contrato.save(update_fields=["contato_web", "updated_at"])

        return Response(
            {"ok": True, "contato_status": associado.contato_status},
            status=status.HTTP_200_OK,
        )


class LegacyAssociadoDoisAuxilio2StatusView(LegacyMobileAPIView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        associado = resolve_mobile_associado(request.user)
        return Response(
            build_auxilio2_payload(request.user, associado=associado),
            status=status.HTTP_200_OK,
        )


class LegacyAssociadoDoisAuxilio2ResumoView(LegacyMobileAPIView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        associado = resolve_mobile_associado(request.user)
        return Response(
            build_auxilio2_payload(request.user, associado=associado),
            status=status.HTTP_200_OK,
        )


class LegacyAssociadoDoisAuxilio2ChargeView(LegacyMobileAPIView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    @transaction.atomic
    def post(self, request):
        associado = resolve_mobile_associado(request.user)
        charge = create_auxilio2_charge(request.user, associado=associado)
        payload = build_auxilio2_payload(request.user, associado=associado)
        return Response(
            {
                "ok": True,
                **payload,
                "filiacaoId": charge.id,
            },
            status=status.HTTP_200_OK,
        )
