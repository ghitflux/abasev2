from __future__ import annotations

from contextlib import nullcontext
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.legacy_helpers import (
    LEGACY_DOCUMENT_TYPE_MAP,
    build_legacy_document_path,
)
from apps.accounts.management.commands.import_legacy_data import (
    Command as LegacyImportCommand,
    _date,
    _dec,
    _int,
    _json,
    _map_contrato_status,
    _map_estado_civil,
    _str,
    _ts,
    extract_table_data,
)
from apps.accounts.models import User
from apps.associados.models import Associado, Documento, only_digits
from apps.associados.services import add_months, calculate_contract_dates, day_of_month
from apps.contratos.competencia import (
    collect_competencia_conflicts,
    create_cycle_with_parcelas,
)
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.esteira.models import EsteiraItem, Transicao


DEFAULT_SQL_FILE = (
    Path(__file__).resolve().parents[5] / "scriptsphp" / "agente_cadastros.sql"
)

ASSOCIADO_FLAT_FIELDS = (
    "tipo_documento",
    "nome_completo",
    "rg",
    "orgao_expedidor",
    "email",
    "telefone",
    "data_nascimento",
    "profissao",
    "estado_civil",
    "cep",
    "logradouro",
    "numero",
    "complemento",
    "bairro",
    "cidade",
    "uf",
    "orgao_publico",
    "matricula_orgao",
    "situacao_servidor",
    "banco",
    "agencia",
    "conta",
    "tipo_conta",
    "chave_pix",
    "cargo",
    "agente_responsavel_id",
    "agente_filial",
    "auxilio_taxa",
    "auxilio_data_envio",
    "auxilio_status",
    "observacao",
    "anticipations_json",
    "documents_json",
)

CONTRATO_SNAPSHOT_FIELDS = (
    "contrato_mensalidade",
    "contrato_prazo_meses",
    "contrato_taxa_antecipacao",
    "contrato_margem_disponivel",
    "contrato_data_aprovacao",
    "contrato_data_envio_primeira",
    "contrato_valor_antecipacao",
    "contrato_status_contrato",
    "contrato_mes_averbacao",
    "contrato_codigo_contrato",
    "contrato_doacao_associado",
    "calc_valor_bruto",
    "calc_liquido_cc",
    "calc_prazo_antecipacao",
    "calc_mensalidade_associativa",
)

class Command(BaseCommand):
    help = (
        "Importa os cadastros legados de agente_cadastros para o formato operacional "
        "atual (Associado + Contrato + Ciclo + Parcela + Esteira + Transicao)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(DEFAULT_SQL_FILE),
            help="Caminho para o dump SQL contendo a tabela agente_cadastros.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Limita a quantidade de linhas processadas, útil para teste.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Processa a importação e desfaz a transação no final.",
        )
        parser.add_argument(
            "--fallback-agent-email",
            help=(
                "Email do usuário AGENTE a ser usado quando o agente legado "
                "não puder ser resolvido pelos snapshots."
            ),
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"]).expanduser()
        if not file_path.exists():
            raise CommandError(f"Arquivo SQL não encontrado: {file_path}")

        sql_text = file_path.read_text(encoding="utf-8")
        rows = extract_table_data(sql_text, "agente_cadastros")
        if not rows:
            raise CommandError(
                f"Nenhum INSERT de `agente_cadastros` encontrado em {file_path}"
            )

        rows.sort(key=self._row_sort_key)
        limit = options.get("limit")
        if limit:
            rows = rows[:limit]

        self._fallback_agent_id = self._resolve_fallback_agent_id(
            options.get("fallback_agent_email")
        )
        self._bootstrap_lookup_helpers()

        summary = {
            "rows_total": 0,
            "associados_created": 0,
            "associados_updated": 0,
            "associados_restored": 0,
            "contratos_created": 0,
            "contratos_restored": 0,
            "contratos_soft_deleted": 0,
            "ciclos_created": 0,
            "parcelas_created": 0,
            "esteiras_created": 0,
            "transicoes_created": 0,
            "documentos_created": 0,
            "competencia_conflicts": 0,
            "rows_skipped": 0,
            "errors": 0,
        }

        context = transaction.atomic() if options["dry_run"] else nullcontext()
        with context:
            self._import_rows(rows, summary)
            if options["dry_run"]:
                transaction.set_rollback(True)

        self.stdout.write(
            "Resumo import_legacy_associados_current_flow: "
            + ", ".join(f"{key}={value}" for key, value in summary.items())
        )
        self.summary = summary

    def _bootstrap_lookup_helpers(self):
        lookup = LegacyImportCommand()
        lookup.stdout.write = lambda *_args, **_kwargs: None
        lookup.stderr.write = lambda *_args, **_kwargs: None
        lookup._user_map = {}
        lookup._role_map = {}
        lookup._cad_map = {}
        lookup._refi_map = {}
        lookup._pag_map = {}
        lookup._tes_pag_map = {}
        lookup._doc_issue_map = {}
        lookup._esteira_map = {}
        lookup._legacy_user_rows = {}
        lookup._agent_lookup = {}
        lookup._agent_first_token_lookup = {}
        lookup._agent_lookup_built = False
        lookup._build_agent_lookup()
        self._legacy_lookup = lookup
        self._default_actor = self._resolve_default_actor()

    def _resolve_default_actor(self) -> User:
        actor = (
            User.objects.filter(roles__codigo="ADMIN").distinct().order_by("id").first()
            or User.objects.filter(roles__codigo="AGENTE")
            .distinct()
            .order_by("id")
            .first()
            or User.objects.order_by("id").first()
        )
        if not actor:
            raise CommandError(
                "Nenhum usuário disponível para registrar as transições da esteira."
            )
        return actor

    def _resolve_fallback_agent_id(self, email: str | None) -> int | None:
        if not email:
            return None
        agent = (
            User.objects.filter(email__iexact=email, roles__codigo="AGENTE")
            .distinct()
            .first()
        )
        if not agent:
            raise CommandError(
                f"Usuário AGENTE não encontrado para --fallback-agent-email={email}"
            )
        return agent.pk

    def _resolve_agent_user_id(self, *snapshots: str) -> int | None:
        resolved = self._legacy_lookup._resolve_agent_user_id(*snapshots)
        if resolved:
            return resolved
        return self._fallback_agent_id

    def _row_sort_key(self, row: dict) -> tuple[date, int]:
        return (
            _date(row.get("contrato_data_aprovacao"))
            or _date(row.get("contrato_data_envio_primeira"))
            or date.min,
            _int(row.get("id")) or 0,
        )

    def _import_rows(self, rows: list[dict], summary: dict[str, int]):
        for row in rows:
            summary["rows_total"] += 1
            try:
                with transaction.atomic():
                    self._import_row(row, summary)
            except Exception as exc:
                summary["errors"] += 1
                self.stderr.write(
                    f"Falha ao importar agente_cadastros.id={row.get('id')}: {exc}"
                )

    def _import_row(self, row: dict, summary: dict[str, int]):
        cpf_cnpj = only_digits(_str(row.get("cpf_cnpj")))
        if not cpf_cnpj:
            summary["rows_skipped"] += 1
            return

        contract_status = _map_contrato_status(_str(row.get("contrato_status_contrato")))
        agent_pk = self._resolve_agent_user_id(
            _str(row.get("agente_responsavel")),
            _str(row.get("agente_filial")),
        )
        raw_documents = _json(row.get("documents_json"))

        (
            associado,
            associado_created,
            associado_updated,
            associado_restored,
        ) = self._ensure_associado(row, cpf_cnpj, agent_pk, contract_status)

        summary["associados_created"] += int(associado_created)
        summary["associados_updated"] += int(associado_updated)
        summary["associados_restored"] += int(associado_restored)

        existing_contract_snapshot = self._capture_contract_snapshot(associado)
        had_existing_contracts = Contrato.all_objects.filter(associado=associado).exists()

        contrato, contrato_created, contrato_restored = self._ensure_contrato(
            associado=associado,
            row=row,
            agent_pk=agent_pk,
        )
        summary["contratos_created"] += int(contrato_created)
        summary["contratos_restored"] += int(contrato_restored)

        if contrato and had_existing_contracts and contrato_created:
            self._restore_contract_snapshot(associado, existing_contract_snapshot)

        if contrato:
            schedule_conflicts = self._collect_schedule_conflicts(contrato=contrato, row=row)
            if schedule_conflicts:
                summary["competencia_conflicts"] += 1
                if contrato_created and had_existing_contracts and contrato.deleted_at is None:
                    contrato.soft_delete()
                    summary["contratos_soft_deleted"] += 1
                self.stderr.write(
                    (
                        "Agenda ignorada para contrato {codigo} por conflito de competência: "
                        "{months}"
                    ).format(
                        codigo=contrato.codigo,
                        months=", ".join(
                            sorted({item["referencia_mes"] for item in schedule_conflicts})
                        ),
                    )
                )
            else:
                _ciclo, ciclo_created, parcelas_created = self._ensure_ciclo(
                    contrato=contrato,
                    row=row,
                )
                summary["ciclos_created"] += int(ciclo_created)
                summary["parcelas_created"] += parcelas_created
                if not ciclo_created:
                    summary["parcelas_created"] += self._ensure_parcelas(
                        contrato=contrato,
                        row=row,
                    )

        esteira_created, transicao_created = self._ensure_esteira(
            associado=associado,
            contract_status=contract_status,
            legacy_created_at=_ts(row.get("created_at")),
            agent_pk=agent_pk,
        )
        summary["esteiras_created"] += int(esteira_created)
        summary["transicoes_created"] += int(transicao_created)

        summary["documentos_created"] += self._ensure_documentos(
            associado=associado,
            raw_documents=raw_documents,
            contract_status=contract_status,
            legacy_created_at=_ts(row.get("created_at")),
            legacy_updated_at=_ts(row.get("updated_at")),
        )

        if raw_documents is not None:
            Associado.all_objects.filter(pk=associado.pk).update(
                documents_json=raw_documents,
                updated_at=timezone.now(),
            )

    def _build_associado_defaults(
        self,
        row: dict,
        cpf_cnpj: str,
        agent_pk: int | None,
        contract_status: str,
    ) -> dict:
        doc_type = (_str(row.get("doc_type")) or Associado.TipoDocumento.CPF).upper()
        tipo_conta = (_str(row.get("account_type")) or "").lower()
        if tipo_conta not in {
            "",
            "corrente",
            "poupanca",
            "salario",
        }:
            tipo_conta = ""

        data_aprovacao = _date(row.get("contrato_data_aprovacao"))
        data_primeira = _date(row.get("contrato_data_envio_primeira"))
        mes_averbacao = _date(row.get("contrato_mes_averbacao"))

        if not (data_aprovacao and data_primeira and mes_averbacao):
            calc_aprovacao, calc_primeira, calc_mes_averbacao = calculate_contract_dates(
                data_aprovacao
            )
            data_aprovacao = data_aprovacao or calc_aprovacao
            data_primeira = data_primeira or calc_primeira
            mes_averbacao = mes_averbacao or calc_mes_averbacao

        return {
            "tipo_documento": (
                Associado.TipoDocumento.CNPJ
                if doc_type == Associado.TipoDocumento.CNPJ
                else Associado.TipoDocumento.CPF
            ),
            "cpf_cnpj": cpf_cnpj,
            "nome_completo": _str(row.get("full_name"))[:255],
            "rg": _str(row.get("rg"))[:30],
            "orgao_expedidor": _str(row.get("orgao_expedidor"))[:80],
            "email": _str(row.get("email"))[:254],
            "telefone": _str(row.get("cellphone"))[:30],
            "data_nascimento": _date(row.get("birth_date")),
            "profissao": _str(row.get("profession"))[:120],
            "estado_civil": _map_estado_civil(_str(row.get("marital_status"))),
            "cep": _str(row.get("cep"))[:12],
            "logradouro": _str(row.get("address"))[:255],
            "numero": _str(row.get("address_number"))[:60],
            "complemento": _str(row.get("complement"))[:120],
            "bairro": _str(row.get("neighborhood"))[:120],
            "cidade": _str(row.get("city"))[:120],
            "uf": _str(row.get("uf")).upper()[:2],
            "orgao_publico": _str(row.get("orgao_publico"))[:160],
            "matricula_orgao": _str(row.get("matricula_servidor_publico"))[:60],
            "situacao_servidor": _str(row.get("situacao_servidor"))[:80],
            "banco": _str(row.get("bank_name"))[:100],
            "agencia": _str(row.get("bank_agency"))[:20],
            "conta": _str(row.get("bank_account"))[:30],
            "tipo_conta": tipo_conta,
            "chave_pix": _str(row.get("pix_key"))[:120],
            "cargo": (_str(row.get("profession")) or "")[:120],
            "contrato_mensalidade": _dec(row.get("contrato_mensalidade")),
            "contrato_prazo_meses": _int(row.get("contrato_prazo_meses")),
            "contrato_taxa_antecipacao": _dec(row.get("contrato_taxa_antecipacao")),
            "contrato_margem_disponivel": _dec(row.get("contrato_margem_disponivel")),
            "contrato_data_aprovacao": data_aprovacao,
            "contrato_data_envio_primeira": data_primeira,
            "contrato_valor_antecipacao": _dec(row.get("contrato_valor_antecipacao")),
            "contrato_status_contrato": contract_status,
            "contrato_mes_averbacao": mes_averbacao,
            "contrato_codigo_contrato": _str(row.get("contrato_codigo_contrato"))[:80],
            "contrato_doacao_associado": _dec(row.get("contrato_doacao_associado")),
            "calc_valor_bruto": _dec(row.get("calc_valor_bruto")),
            "calc_liquido_cc": _dec(row.get("calc_liquido_cc")),
            "calc_prazo_antecipacao": _int(row.get("calc_prazo_antecipacao")),
            "calc_mensalidade_associativa": _dec(
                row.get("calc_mensalidade_associativa")
            ),
            "anticipations_json": _json(row.get("anticipations_json")),
            "documents_json": _json(row.get("documents_json")),
            "status": self._map_associado_status(contract_status),
            "agente_responsavel_id": agent_pk,
            "agente_filial": _str(row.get("agente_filial"))[:160],
            "auxilio_taxa": _dec(row.get("auxilio_taxa")) or Decimal("10.00"),
            "auxilio_data_envio": _date(row.get("auxilio_data_envio")),
            "auxilio_status": _str(row.get("auxilio_status"))[:80],
            "observacao": _str(row.get("observacoes")),
        }

    def _ensure_associado(
        self,
        row: dict,
        cpf_cnpj: str,
        agent_pk: int | None,
        contract_status: str,
    ) -> tuple[Associado, bool, bool, bool]:
        defaults = self._build_associado_defaults(row, cpf_cnpj, agent_pk, contract_status)
        associado = Associado.all_objects.filter(cpf_cnpj=cpf_cnpj).first()
        created = False
        updated = False
        restored = False

        if not associado:
            associado = Associado.objects.create(**defaults)
            self._apply_timestamps(
                model=Associado,
                obj_id=associado.pk,
                created_at=_ts(row.get("created_at")),
                updated_at=_ts(row.get("updated_at")),
            )
            return associado, True, False, False

        if associado.deleted_at:
            associado.restore()
            restored = True

        update_fields = []
        for field in ASSOCIADO_FLAT_FIELDS:
            new_value = defaults.get(field)
            current_value = getattr(associado, field)
            if self._is_blank(current_value) and not self._is_blank(new_value):
                setattr(associado, field, new_value)
                update_fields.append(field)

        if associated_should_upgrade_status := (
            associado.status == Associado.Status.CADASTRADO
            and defaults["status"] != Associado.Status.CADASTRADO
        ):
            associado.status = defaults["status"]
            update_fields.append("status")

        if update_fields or restored or associated_should_upgrade_status:
            associado.save(update_fields=[*set(update_fields), "updated_at"])
            updated = bool(update_fields or associated_should_upgrade_status)

        return associado, created, updated, restored

    def _ensure_contrato(
        self,
        associado: Associado,
        row: dict,
        agent_pk: int | None,
    ) -> tuple[Contrato | None, bool, bool]:
        codigo = _str(row.get("contrato_codigo_contrato"))[:40]
        if not codigo:
            return None, False, False

        contrato = Contrato.all_objects.select_related("associado").filter(codigo=codigo).first()
        if contrato:
            if contrato.associado_id != associado.id:
                raise ValueError(
                    f"Contrato {codigo} já pertence ao associado {contrato.associado_id}"
                )
            restored = False
            if contrato.deleted_at:
                contrato.restore()
                restored = True
            return contrato, False, restored

        data_aprovacao = _date(row.get("contrato_data_aprovacao"))
        data_primeira = _date(row.get("contrato_data_envio_primeira"))
        mes_averbacao = _date(row.get("contrato_mes_averbacao"))
        calc_aprovacao, calc_primeira, calc_mes_averbacao = calculate_contract_dates(
            data_aprovacao
        )
        data_aprovacao = data_aprovacao or calc_aprovacao
        data_primeira = data_primeira or calc_primeira
        mes_averbacao = mes_averbacao or calc_mes_averbacao

        contrato = Contrato.objects.create(
            associado=associado,
            agente_id=agent_pk,
            codigo=codigo,
            valor_bruto=_dec(row.get("calc_valor_bruto")) or Decimal("0.00"),
            valor_liquido=_dec(row.get("calc_liquido_cc")) or Decimal("0.00"),
            valor_mensalidade=_dec(row.get("contrato_mensalidade")) or Decimal("0.00"),
            prazo_meses=_int(row.get("contrato_prazo_meses")) or 3,
            taxa_antecipacao=_dec(row.get("contrato_taxa_antecipacao")) or Decimal("0.00"),
            margem_disponivel=_dec(row.get("contrato_margem_disponivel"))
            or Decimal("0.00"),
            valor_total_antecipacao=_dec(row.get("contrato_valor_antecipacao"))
            or Decimal("0.00"),
            doacao_associado=_dec(row.get("contrato_doacao_associado"))
            or Decimal("0.00"),
            status=_map_contrato_status(_str(row.get("contrato_status_contrato"))),
            data_contrato=data_aprovacao or timezone.localdate(),
            data_aprovacao=data_aprovacao,
            data_primeira_mensalidade=data_primeira,
            mes_averbacao=mes_averbacao,
            contato_web=True,
            termos_web=True,
            auxilio_liberado_em=_date(row.get("auxilio_data_envio")),
        )

        legacy_total = _dec(row.get("contrato_valor_antecipacao"))
        created_at = _ts(row.get("created_at"))
        updated_at = _ts(row.get("updated_at"))
        updates = {}
        if legacy_total is not None:
            updates["valor_total_antecipacao"] = legacy_total
        if created_at:
            updates["created_at"] = created_at
        if updated_at:
            updates["updated_at"] = updated_at
        if updates:
            Contrato.all_objects.filter(pk=contrato.pk).update(**updates)
            contrato.refresh_from_db()
            associado.sync_contrato_snapshot(contrato)

        return contrato, True, False

    def _expected_schedule_references(self, contrato: Contrato, row: dict) -> list[date]:
        prazo_meses = contrato.prazo_meses or _int(row.get("contrato_prazo_meses")) or 3
        data_primeira = contrato.data_primeira_mensalidade
        if not data_primeira:
            _approval, calc_primeira, _mes_averbacao = calculate_contract_dates(
                contrato.data_aprovacao
            )
            data_primeira = calc_primeira
        primeira_referencia = data_primeira.replace(day=1)
        return [
            add_months(primeira_referencia, indice)
            for indice in range(prazo_meses)
        ]

    def _collect_schedule_conflicts(
        self,
        *,
        contrato: Contrato,
        row: dict,
    ) -> list[dict[str, object]]:
        referencias = self._expected_schedule_references(contrato, row)
        own_parcela_ids = list(
            Parcela.all_objects.filter(ciclo__contrato=contrato).values_list("id", flat=True)
        )
        return collect_competencia_conflicts(
            associado_id=contrato.associado_id,
            referencias=referencias,
            exclude_parcela_ids=own_parcela_ids,
        )

    def _ensure_ciclo(self, contrato: Contrato, row: dict) -> tuple[Ciclo, bool, int]:
        ciclo = Ciclo.all_objects.filter(contrato=contrato, numero=1).first()
        if ciclo:
            if ciclo.deleted_at:
                ciclo.restore()
            return ciclo, False, 0

        prazo_meses = contrato.prazo_meses or _int(row.get("contrato_prazo_meses")) or 3
        data_primeira = contrato.data_primeira_mensalidade
        if not data_primeira:
            _approval, calc_primeira, _mes_averbacao = calculate_contract_dates(
                contrato.data_aprovacao
            )
            data_primeira = calc_primeira

        primeira_referencia = data_primeira.replace(day=1)
        data_fim = add_months(primeira_referencia, max(prazo_meses - 1, 0))
        ciclo, parcelas = create_cycle_with_parcelas(
            contrato=contrato,
            numero=1,
            competencia_inicial=primeira_referencia,
            parcelas_total=prazo_meses,
            ciclo_status=self._infer_ciclo_status(
                contract_status=contrato.status,
                data_inicio=primeira_referencia,
                data_fim=data_fim,
            ),
            parcela_status=(
                Parcela.Status.CANCELADO
                if contrato.status == Contrato.Status.CANCELADO
                else Parcela.Status.EM_ABERTO
            ),
            data_vencimento_fn=day_of_month,
            valor_mensalidade=contrato.valor_mensalidade,
            valor_total=contrato.valor_total_antecipacao
            or (contrato.valor_mensalidade * prazo_meses).quantize(Decimal("0.01")),
        )
        self._apply_timestamps(
            model=Ciclo,
            obj_id=ciclo.pk,
            created_at=_ts(row.get("created_at")),
            updated_at=_ts(row.get("updated_at")),
        )
        legacy_created_at = _ts(row.get("created_at"))
        legacy_updated_at = _ts(row.get("updated_at"))
        for parcela in parcelas:
            status = self._infer_parcela_status(
                contract_status=contrato.status,
                referencia_mes=parcela.referencia_mes,
            )
            if parcela.status != status:
                parcela.status = status
                parcela.save(update_fields=["status", "updated_at"])
            self._apply_timestamps(
                model=Parcela,
                obj_id=parcela.pk,
                created_at=legacy_created_at,
                updated_at=legacy_updated_at,
            )
        return ciclo, True, len(parcelas)

    def _ensure_parcelas(self, contrato: Contrato, row: dict) -> int:
        ciclo = Ciclo.all_objects.get(contrato=contrato, numero=1)
        prazo_meses = contrato.prazo_meses or _int(row.get("contrato_prazo_meses")) or 3
        data_primeira = contrato.data_primeira_mensalidade
        if not data_primeira:
            _approval, calc_primeira, _mes_averbacao = calculate_contract_dates(
                contrato.data_aprovacao
            )
            data_primeira = calc_primeira
        primeira_referencia = data_primeira.replace(day=1)
        created = 0
        legacy_created_at = _ts(row.get("created_at"))
        legacy_updated_at = _ts(row.get("updated_at"))

        for indice in range(prazo_meses):
            numero = indice + 1
            parcela = Parcela.all_objects.filter(ciclo=ciclo, numero=numero).first()
            if parcela:
                if parcela.deleted_at:
                    parcela.restore()
                continue

            referencia = add_months(primeira_referencia, indice)
            parcela = Parcela.objects.create(
                ciclo=ciclo,
                numero=numero,
                referencia_mes=referencia,
                valor=contrato.valor_mensalidade,
                data_vencimento=day_of_month(referencia),
                status=self._infer_parcela_status(
                    contract_status=contrato.status,
                    referencia_mes=referencia,
                ),
            )
            self._apply_timestamps(
                model=Parcela,
                obj_id=parcela.pk,
                created_at=legacy_created_at,
                updated_at=legacy_updated_at,
            )
            created += 1

        return created

    def _ensure_esteira(
        self,
        associado: Associado,
        contract_status: str,
        legacy_created_at: datetime | None,
        agent_pk: int | None,
    ) -> tuple[bool, bool]:
        esteira = EsteiraItem.all_objects.filter(associado=associado).first()
        if esteira:
            if esteira.deleted_at:
                esteira.restore()
            return False, False

        etapa, situacao = self._infer_esteira_state(contract_status)
        esteira = EsteiraItem.objects.create(
            associado=associado,
            etapa_atual=etapa,
            status=situacao,
            concluido_em=legacy_created_at
            if etapa == EsteiraItem.Etapa.CONCLUIDO
            else None,
        )
        self._apply_timestamps(
            model=EsteiraItem,
            obj_id=esteira.pk,
            created_at=legacy_created_at,
            updated_at=legacy_created_at,
        )

        actor = User.objects.filter(pk=agent_pk).first() if agent_pk else None
        actor = actor or self._default_actor
        transicao = Transicao.objects.create(
            esteira_item=esteira,
            acao="importar_legado",
            de_status=EsteiraItem.Etapa.CADASTRO,
            para_status=etapa,
            de_situacao=EsteiraItem.Situacao.AGUARDANDO,
            para_situacao=situacao,
            realizado_por=actor,
            observacao="Cadastro legado importado para o fluxo atual.",
            realizado_em=legacy_created_at or timezone.now(),
        )
        self._apply_timestamps(
            model=Transicao,
            obj_id=transicao.pk,
            created_at=legacy_created_at,
            updated_at=legacy_created_at,
        )
        return True, True

    def _ensure_documentos(
        self,
        associado: Associado,
        raw_documents,
        contract_status: str,
        legacy_created_at: datetime | None,
        legacy_updated_at: datetime | None,
    ) -> int:
        if not isinstance(raw_documents, list):
            return 0

        created = 0

        for item in raw_documents:
            if not isinstance(item, dict):
                continue
            relative_path = self._legacy_document_path(item)
            if not relative_path:
                continue

            tipo = LEGACY_DOCUMENT_TYPE_MAP.get(
                str(item.get("field") or "").strip().lower(),
                Documento.Tipo.OUTRO,
            )
            documento = Documento.all_objects.filter(
                associado=associado,
                tipo=tipo,
                arquivo=relative_path,
            ).first()
            if documento:
                if documento.deleted_at:
                    documento.restore()
                continue

            documento = Documento.objects.create(
                associado=associado,
                tipo=tipo,
                arquivo=relative_path,
                status=Documento.Status.APROVADO,
                observacao=str(item.get("original_name") or "")[:500],
            )
            self._apply_timestamps(
                model=Documento,
                obj_id=documento.pk,
                created_at=_ts(item.get("uploaded_at")) or legacy_created_at,
                updated_at=legacy_updated_at or _ts(item.get("uploaded_at")),
            )
            created += 1

        return created

    def _legacy_document_path(self, item: dict) -> str:
        return build_legacy_document_path(item)

    def _capture_contract_snapshot(self, associado: Associado) -> dict:
        return {field: getattr(associado, field) for field in CONTRATO_SNAPSHOT_FIELDS}

    def _restore_contract_snapshot(self, associado: Associado, snapshot: dict):
        Associado.all_objects.filter(pk=associado.pk).update(
            **snapshot,
            updated_at=timezone.now(),
        )

    def _apply_timestamps(
        self,
        model,
        obj_id: int,
        created_at: datetime | None,
        updated_at: datetime | None,
    ):
        updates = {}
        if created_at:
            updates["created_at"] = created_at
        if updated_at:
            updates["updated_at"] = updated_at
        elif created_at:
            updates["updated_at"] = created_at
        if updates:
            model.all_objects.filter(pk=obj_id).update(**updates)

    def _infer_ciclo_status(
        self,
        contract_status: str,
        data_inicio: date,
        data_fim: date,
    ) -> str:
        referencia_atual = timezone.localdate().replace(day=1)
        if contract_status == Contrato.Status.CANCELADO:
            return Ciclo.Status.FECHADO
        if data_fim < referencia_atual:
            return Ciclo.Status.APTO_A_RENOVAR
        if data_inicio > referencia_atual:
            return Ciclo.Status.FUTURO
        return Ciclo.Status.ABERTO

    def _infer_parcela_status(self, contract_status: str, referencia_mes: date) -> str:
        referencia_atual = timezone.localdate().replace(day=1)
        if contract_status == Contrato.Status.CANCELADO:
            return Parcela.Status.CANCELADO
        if referencia_mes > referencia_atual:
            return Parcela.Status.FUTURO
        return Parcela.Status.EM_ABERTO

    def _infer_esteira_state(self, contract_status: str) -> tuple[str, str]:
        if contract_status in {Contrato.Status.ATIVO, Contrato.Status.ENCERRADO}:
            return EsteiraItem.Etapa.CONCLUIDO, EsteiraItem.Situacao.APROVADO
        if contract_status == Contrato.Status.CANCELADO:
            return EsteiraItem.Etapa.CONCLUIDO, EsteiraItem.Situacao.REJEITADO
        return EsteiraItem.Etapa.ANALISE, EsteiraItem.Situacao.AGUARDANDO

    def _map_associado_status(self, contract_status: str) -> str:
        if contract_status == Contrato.Status.ATIVO:
            return Associado.Status.ATIVO
        if contract_status in {Contrato.Status.CANCELADO, Contrato.Status.ENCERRADO}:
            return Associado.Status.INATIVO
        return Associado.Status.EM_ANALISE

    def _is_blank(self, value) -> bool:
        return value in (None, "", [], {})
