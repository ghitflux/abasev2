from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.management.seed_utils import ensure_access_users
from apps.accounts.models import User
from apps.associados.models import Associado, Documento
from apps.associados.services import AssociadoService
from apps.contratos.models import Contrato
from apps.esteira.services import EsteiraService
from apps.refinanciamento.models import Comprovante, Refinanciamento
from apps.tesouraria.models import Confirmacao, Pagamento
from apps.tesouraria.services import ConfirmacaoService, TesourariaService

# CPFs exclusivos para seed de tesouraria (não colidem com seed_demo_data 900000000xx)
SEED_TESO_CPFS = [
    "91000000001",  # teso_sem_link
    "91000000002",  # teso_com_link
    "91000000003",  # teso_ligacao_confirmada
    "91000000004",  # teso_completo_atual
    "91000000005",  # teso_historico_1
    "91000000006",  # teso_historico_2
    "91000000007",  # teso_pendenciado
    "91000000008",  # teso_pag_pago_pix
    "91000000009",  # teso_pag_pago_ted
    "91000000010",  # teso_pag_pendente
    "91000000011",  # teso_pag_cancelado
    "91000000012",  # teso_multi_competencia
]


def _add_months(base: date, months: int) -> date:
    idx = base.month - 1 + months
    return date(base.year + idx // 12, idx % 12 + 1, 1)


def _arquivo(nome: str, conteudo: bytes = b"seed tesouraria") -> SimpleUploadedFile:
    return SimpleUploadedFile(nome, conteudo, content_type="application/pdf")


class Command(BaseCommand):
    help = "Cria dados demo completos para o modulo de tesouraria (confirmacoes e pagamentos)."

    @transaction.atomic
    def handle(self, *args, **options):
        user_specs = ensure_access_users()
        users = {
            role: User.objects.get(email=spec.email)
            for role, spec in user_specs.items()
        }

        self._cleanup()

        hoje = timezone.localdate()
        comp_atual = hoje.replace(day=1)
        comp_anterior = _add_months(comp_atual, -1)
        comp_2_meses = _add_months(comp_atual, -2)

        agente = users["AGENTE"]
        analista = users["ANALISTA"]
        coordenador = users["COORDENADOR"]
        tesoureiro = users["TESOUREIRO"]

        # -------------------------------------------------------
        # Cenário 1: Contrato na tesouraria — sem link de chamada
        # -------------------------------------------------------
        c1 = self._criar_e_levar_tesouraria(
            slug="teso_sem_link",
            nome="Alice Sem Link",
            cpf="91000000001",
            agente=agente,
            analista=analista,
            coordenador=coordenador,
            comp=comp_atual,
        )
        ConfirmacaoService._garantir_registros(c1["contrato"], comp_atual)

        # -------------------------------------------------------
        # Cenário 2: Contrato na tesouraria — link salvo, não confirmado
        # -------------------------------------------------------
        c2 = self._criar_e_levar_tesouraria(
            slug="teso_com_link",
            nome="Bruno Com Link",
            cpf="91000000002",
            agente=agente,
            analista=analista,
            coordenador=coordenador,
            comp=comp_atual,
        )
        ligacao2, _ = ConfirmacaoService._garantir_registros(c2["contrato"], comp_atual)
        ligacao2.link_chamada = "https://meet.google.com/seed-com-link-abc"
        ligacao2.save(update_fields=["link_chamada", "updated_at"])

        # -------------------------------------------------------
        # Cenário 3: Ligação confirmada, averbação pendente
        # -------------------------------------------------------
        c3 = self._criar_e_levar_tesouraria(
            slug="teso_ligacao_confirmada",
            nome="Carla Ligacao Ok",
            cpf="91000000003",
            agente=agente,
            analista=analista,
            coordenador=coordenador,
            comp=comp_atual,
        )
        ligacao3, _ = ConfirmacaoService._garantir_registros(c3["contrato"], comp_atual)
        ligacao3.link_chamada = "https://meet.google.com/seed-ligacao-ok-def"
        ligacao3.save(update_fields=["link_chamada", "updated_at"])
        ligacao3.confirmar(tesoureiro, "Ligacao confirmada no seed tesouraria.")

        # -------------------------------------------------------
        # Cenário 4: Ligação e averbação confirmadas (completo, contrato ativo)
        # -------------------------------------------------------
        c4 = self._criar_efetivado(
            slug="teso_completo_atual",
            nome="Diego Completo",
            cpf="91000000004",
            agente=agente,
            analista=analista,
            coordenador=coordenador,
            tesoureiro=tesoureiro,
            comp=comp_atual,
        )
        ligacao4, averbacao4 = ConfirmacaoService._garantir_registros(c4["contrato"], comp_atual)
        ligacao4.link_chamada = "https://meet.google.com/seed-completo-ghi"
        ligacao4.save(update_fields=["link_chamada", "updated_at"])
        ligacao4.confirmar(tesoureiro, "Ligacao confirmada — seed completo.")
        averbacao4.confirmar(tesoureiro, "Averbacao confirmada — seed completo.")

        # -------------------------------------------------------
        # Cenário 5: Histórico — competência anterior confirmada, atual pendente
        # -------------------------------------------------------
        c5 = self._criar_efetivado(
            slug="teso_historico_1",
            nome="Eduarda Historico",
            cpf="91000000005",
            agente=agente,
            analista=analista,
            coordenador=coordenador,
            tesoureiro=tesoureiro,
            comp=comp_anterior,
        )
        # Competência anterior: totalmente confirmada
        lig5a, averb5a = ConfirmacaoService._garantir_registros(c5["contrato"], comp_anterior)
        lig5a.link_chamada = "https://meet.google.com/seed-hist1-ant"
        lig5a.save(update_fields=["link_chamada", "updated_at"])
        lig5a.confirmar(tesoureiro, "Ligacao competencia anterior — seed hist1.")
        averb5a.confirmar(tesoureiro, "Averbacao competencia anterior — seed hist1.")
        # Competência atual: link salvo
        lig5b, _ = ConfirmacaoService._garantir_registros(c5["contrato"], comp_atual)
        lig5b.link_chamada = "https://meet.google.com/seed-hist1-atual"
        lig5b.save(update_fields=["link_chamada", "updated_at"])

        # -------------------------------------------------------
        # Cenário 6: Histórico multi-competência (3 meses de registros)
        # -------------------------------------------------------
        c6 = self._criar_efetivado(
            slug="teso_historico_2",
            nome="Felipe Multiplo",
            cpf="91000000006",
            agente=agente,
            analista=analista,
            coordenador=coordenador,
            tesoureiro=tesoureiro,
            comp=comp_2_meses,
        )
        for comp, link_suffix, confirmar in [
            (comp_2_meses, "2m", True),
            (comp_anterior, "1m", True),
            (comp_atual, "atual", False),
        ]:
            lig, averb = ConfirmacaoService._garantir_registros(c6["contrato"], comp)
            lig.link_chamada = f"https://meet.google.com/seed-multi-{link_suffix}"
            lig.save(update_fields=["link_chamada", "updated_at"])
            if confirmar:
                lig.confirmar(tesoureiro, f"Ligacao {comp} — seed multi.")
                averb.confirmar(tesoureiro, f"Averbacao {comp} — seed multi.")

        # -------------------------------------------------------
        # Cenário 7: Contrato pendenciado na tesouraria (congelado)
        # -------------------------------------------------------
        c7 = self._criar_e_levar_tesouraria(
            slug="teso_pendenciado",
            nome="Giovana Pendenciada",
            cpf="91000000007",
            agente=agente,
            analista=analista,
            coordenador=coordenador,
            comp=comp_atual,
        )
        TesourariaService.congelar_contrato(
            c7["contrato"].id,
            "Documentacao bancaria divergente. Aguardando regularizacao.",
            tesoureiro,
        )

        # -------------------------------------------------------
        # Cenário 8: Pagamento realizado via PIX
        # -------------------------------------------------------
        c8 = self._criar_efetivado(
            slug="teso_pag_pix",
            nome="Henrique Pago Pix",
            cpf="91000000008",
            agente=agente,
            analista=analista,
            coordenador=coordenador,
            tesoureiro=tesoureiro,
            comp=comp_anterior,
        )
        Pagamento.objects.create(
            cadastro=c8["associado"],
            created_by=tesoureiro,
            contrato_codigo=c8["contrato"].codigo,
            contrato_valor_antecipacao=c8["contrato"].valor_liquido,
            contrato_margem_disponivel=c8["contrato"].margem_disponivel,
            cpf_cnpj=c8["associado"].cpf_cnpj,
            full_name=c8["associado"].nome_completo,
            agente_responsavel=agente.full_name,
            status=Pagamento.Status.PAGO,
            valor_pago=c8["contrato"].valor_liquido,
            paid_at=timezone.now() - timedelta(days=35),
            forma_pagamento="pix",
            comprovante_path=f"comprovantes/pix_{c8['associado'].cpf_cnpj}.pdf",
            comprovante_associado_path=f"comprovantes/assoc_{c8['associado'].cpf_cnpj}.pdf",
            comprovante_agente_path=f"comprovantes/agente_{c8['associado'].cpf_cnpj}.pdf",
            notes="Pagamento via PIX realizado no seed tesouraria.",
        )

        # -------------------------------------------------------
        # Cenário 9: Pagamento realizado via TED
        # -------------------------------------------------------
        c9 = self._criar_efetivado(
            slug="teso_pag_ted",
            nome="Isabela Paga Ted",
            cpf="91000000009",
            agente=agente,
            analista=analista,
            coordenador=coordenador,
            tesoureiro=tesoureiro,
            comp=comp_anterior,
        )
        Pagamento.objects.create(
            cadastro=c9["associado"],
            created_by=tesoureiro,
            contrato_codigo=c9["contrato"].codigo,
            contrato_valor_antecipacao=c9["contrato"].valor_liquido,
            contrato_margem_disponivel=c9["contrato"].margem_disponivel,
            cpf_cnpj=c9["associado"].cpf_cnpj,
            full_name=c9["associado"].nome_completo,
            agente_responsavel=agente.full_name,
            status=Pagamento.Status.PAGO,
            valor_pago=c9["contrato"].valor_liquido,
            paid_at=timezone.now() - timedelta(days=33),
            forma_pagamento="ted",
            comprovante_path=f"comprovantes/ted_{c9['associado'].cpf_cnpj}.pdf",
            comprovante_associado_path=f"comprovantes/assoc_{c9['associado'].cpf_cnpj}.pdf",
            comprovante_agente_path=f"comprovantes/agente_{c9['associado'].cpf_cnpj}.pdf",
            notes="Pagamento via TED realizado no seed tesouraria.",
        )

        # -------------------------------------------------------
        # Cenário 10: Pagamento pendente (aguardando processamento)
        # -------------------------------------------------------
        c10 = self._criar_e_levar_tesouraria(
            slug="teso_pag_pendente",
            nome="Jonas Pagamento Pendente",
            cpf="91000000010",
            agente=agente,
            analista=analista,
            coordenador=coordenador,
            comp=comp_atual,
        )
        contrato10 = c10["contrato"]
        Pagamento.objects.create(
            cadastro=c10["associado"],
            created_by=tesoureiro,
            contrato_codigo=contrato10.codigo,
            contrato_valor_antecipacao=contrato10.valor_liquido,
            contrato_margem_disponivel=contrato10.margem_disponivel,
            cpf_cnpj=c10["associado"].cpf_cnpj,
            full_name=c10["associado"].nome_completo,
            agente_responsavel=agente.full_name,
            status=Pagamento.Status.PENDENTE,
            valor_pago=contrato10.valor_liquido,
            paid_at=None,
            forma_pagamento="pix",
            notes="Aguardando confirmacao dos dados bancarios para liberacao.",
        )

        # -------------------------------------------------------
        # Cenário 11: Pagamento cancelado
        # -------------------------------------------------------
        c11 = self._criar_efetivado(
            slug="teso_pag_cancelado",
            nome="Larissa Pag Cancelado",
            cpf="91000000011",
            agente=agente,
            analista=analista,
            coordenador=coordenador,
            tesoureiro=tesoureiro,
            comp=comp_anterior,
        )
        Pagamento.objects.create(
            cadastro=c11["associado"],
            created_by=tesoureiro,
            contrato_codigo=c11["contrato"].codigo,
            contrato_valor_antecipacao=c11["contrato"].valor_liquido,
            contrato_margem_disponivel=c11["contrato"].margem_disponivel,
            cpf_cnpj=c11["associado"].cpf_cnpj,
            full_name=c11["associado"].nome_completo,
            agente_responsavel=agente.full_name,
            status=Pagamento.Status.CANCELADO,
            valor_pago=c11["contrato"].valor_liquido,
            paid_at=None,
            forma_pagamento="pix",
            notes="Cancelado por divergencia nos dados bancarios — conta encerrada.",
        )

        # -------------------------------------------------------
        # Cenário 12: Multi-competência com pagamentos distintos por ciclo
        # -------------------------------------------------------
        c12 = self._criar_efetivado(
            slug="teso_multi_competencia",
            nome="Marcos Multi Comp",
            cpf="91000000012",
            agente=agente,
            analista=analista,
            coordenador=coordenador,
            tesoureiro=tesoureiro,
            comp=comp_2_meses,
        )
        # Pagamento do ciclo anterior (pago)
        Pagamento.objects.create(
            cadastro=c12["associado"],
            created_by=tesoureiro,
            contrato_codigo=c12["contrato"].codigo,
            contrato_valor_antecipacao=c12["contrato"].valor_liquido,
            contrato_margem_disponivel=c12["contrato"].margem_disponivel,
            cpf_cnpj=c12["associado"].cpf_cnpj,
            full_name=c12["associado"].nome_completo,
            agente_responsavel=agente.full_name,
            status=Pagamento.Status.PAGO,
            valor_pago=c12["contrato"].valor_liquido,
            paid_at=timezone.now() - timedelta(days=65),
            forma_pagamento="pix",
            comprovante_path=f"comprovantes/multi_ciclo1_{c12['associado'].cpf_cnpj}.pdf",
            notes="Primeiro pagamento — seed multi-competencia.",
        )
        # Segundo pagamento (também pago, mês seguinte)
        Pagamento.objects.create(
            cadastro=c12["associado"],
            created_by=tesoureiro,
            contrato_codigo=c12["contrato"].codigo,
            contrato_valor_antecipacao=c12["contrato"].valor_liquido,
            contrato_margem_disponivel=c12["contrato"].margem_disponivel,
            cpf_cnpj=c12["associado"].cpf_cnpj,
            full_name=c12["associado"].nome_completo,
            agente_responsavel=agente.full_name,
            status=Pagamento.Status.PAGO,
            valor_pago=c12["contrato"].valor_liquido,
            paid_at=timezone.now() - timedelta(days=35),
            forma_pagamento="pix",
            comprovante_path=f"comprovantes/multi_ciclo2_{c12['associado'].cpf_cnpj}.pdf",
            notes="Segundo pagamento — seed multi-competencia.",
        )

        self._imprimir_resumo()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _criar_associado_base(
        self,
        *,
        slug: str,
        nome: str,
        cpf: str,
        agente: User,
        comp: date,
        mensalidade: Decimal,
    ) -> dict[str, object]:
        associado = AssociadoService.criar_associado_completo(
            {
                "cpf_cnpj": cpf,
                "nome_completo": nome,
                "rg": f"RG-{cpf[-4:]}",
                "orgao_expedidor": "SSP-PI",
                "data_nascimento": date(1982, 6, 15) + timedelta(days=int(cpf[-3:])),
                "profissao": "Servidor publico",
                "estado_civil": Associado.EstadoCivil.CASADO,
                "cargo": "Tecnico administrativo",
                "observacao": f"Seed tesouraria: {slug}.",
                "endereco": {
                    "cep": "64001000",
                    "logradouro": f"Av. Seed Tesouraria, {int(cpf[-3:])}",
                    "numero": cpf[-3:],
                    "complemento": "",
                    "bairro": "Jockey",
                    "cidade": "Teresina",
                    "uf": "PI",
                },
                "dados_bancarios": {
                    "banco": "Caixa Economica Federal",
                    "agencia": cpf[-4:],
                    "conta": f"{cpf[-5:]}-1",
                    "tipo_conta": "corrente",
                    "chave_pix": f"{cpf}",
                },
                "contato": {
                    "celular": f"86988{cpf[-6:]}",
                    "email": f"{slug}@tesouraria.seed",
                    "orgao_publico": "SEFAZ-PI",
                    "situacao_servidor": "ativo",
                    "matricula_servidor": f"TESO-{cpf[-6:]}",
                },
                "documentos_payload": [
                    {
                        "tipo": Documento.Tipo.DOCUMENTO_FRENTE,
                        "arquivo": _arquivo(f"{slug}_frente.pdf"),
                    },
                    {
                        "tipo": Documento.Tipo.DOCUMENTO_VERSO,
                        "arquivo": _arquivo(f"{slug}_verso.pdf"),
                    },
                    {
                        "tipo": Documento.Tipo.COMPROVANTE_RESIDENCIA,
                        "arquivo": _arquivo(f"{slug}_residencia.pdf"),
                    },
                ],
                "contrato": {
                    "valor_bruto_total": mensalidade * Decimal("3"),
                    "valor_liquido": mensalidade * Decimal("2.4"),
                    "prazo_meses": 3,
                    "taxa_antecipacao": Decimal("1.80"),
                    "mensalidade": mensalidade,
                    "margem_disponivel": mensalidade * Decimal("0.85"),
                    "data_aprovacao": comp - timedelta(days=10),
                    "data_primeira_mensalidade": comp,
                    "mes_averbacao": comp,
                    "doacao_associado": Decimal("30.00"),
                },
            },
            agente,
        )
        associado.documentos.update(status=Documento.Status.APROVADO)
        contrato = associado.contratos.order_by("-created_at").first()
        contrato.data_contrato = comp - timedelta(days=15)
        contrato.save(update_fields=["data_contrato", "updated_at"])
        return {"associado": associado, "contrato": contrato, "esteira": associado.esteira_item}

    def _criar_e_levar_tesouraria(
        self,
        *,
        slug: str,
        nome: str,
        cpf: str,
        agente: User,
        analista: User,
        coordenador: User,
        comp: date,
        mensalidade: Decimal | None = None,
    ) -> dict[str, object]:
        if mensalidade is None:
            mensalidade = Decimal("480.00") + Decimal(str(int(cpf[-3:]) % 100 * 2))
        dados = self._criar_associado_base(
            slug=slug,
            nome=nome,
            cpf=cpf,
            agente=agente,
            comp=comp,
            mensalidade=mensalidade,
        )
        EsteiraService.assumir(dados["esteira"], analista)
        EsteiraService.aprovar(dados["esteira"], analista, f"Aprovado analise — seed {slug}.")
        dados["esteira"].refresh_from_db()
        return dados

    def _criar_efetivado(
        self,
        *,
        slug: str,
        nome: str,
        cpf: str,
        agente: User,
        analista: User,
        coordenador: User,
        tesoureiro: User,
        comp: date,
        mensalidade: Decimal | None = None,
    ) -> dict[str, object]:
        dados = self._criar_e_levar_tesouraria(
            slug=slug,
            nome=nome,
            cpf=cpf,
            agente=agente,
            analista=analista,
            coordenador=coordenador,
            comp=comp,
            mensalidade=mensalidade,
        )
        TesourariaService.efetivar_contrato(
            dados["contrato"].id,
            _arquivo(f"{slug}_comprov_assoc.pdf"),
            _arquivo(f"{slug}_comprov_agente.pdf"),
            tesoureiro,
        )
        dados["contrato"].refresh_from_db()
        dados["associado"].refresh_from_db()
        return dados

    def _cleanup(self):
        associado_ids = list(
            Associado.all_objects.filter(cpf_cnpj__in=SEED_TESO_CPFS).values_list("id", flat=True)
        )
        if not associado_ids:
            return

        contrato_ids = list(
            Contrato.all_objects.filter(associado_id__in=associado_ids).values_list("id", flat=True)
        )
        refinanciamento_ids = list(
            Refinanciamento.all_objects.filter(
                Q(associado_id__in=associado_ids) | Q(contrato_origem_id__in=contrato_ids)
            ).values_list("id", flat=True)
        )

        if contrato_ids:
            Confirmacao.all_objects.filter(contrato_id__in=contrato_ids).hard_delete()
        if refinanciamento_ids or contrato_ids:
            Comprovante.all_objects.filter(
                Q(refinanciamento_id__in=refinanciamento_ids) | Q(contrato_id__in=contrato_ids)
            ).hard_delete()
        if refinanciamento_ids:
            Refinanciamento.all_objects.filter(id__in=refinanciamento_ids).hard_delete()
        if contrato_ids:
            Contrato.all_objects.filter(id__in=contrato_ids).hard_delete()

        Pagamento.all_objects.filter(cadastro_id__in=associado_ids).hard_delete()
        Associado.all_objects.filter(id__in=associado_ids).hard_delete()

    def _imprimir_resumo(self):
        n_assoc = Associado.objects.filter(cpf_cnpj__in=SEED_TESO_CPFS).count()
        n_contratos = Contrato.objects.filter(associado__cpf_cnpj__in=SEED_TESO_CPFS).count()
        n_confirmacoes = Confirmacao.objects.filter(
            contrato__associado__cpf_cnpj__in=SEED_TESO_CPFS
        ).count()
        n_pagamentos = Pagamento.objects.filter(cpf_cnpj__in=SEED_TESO_CPFS).count()

        self.stdout.write(self.style.SUCCESS("Seed tesouraria concluido com sucesso."))
        self.stdout.write("")
        self.stdout.write("Cenarios criados:")
        self.stdout.write("  [sem_link]           Alice Sem Link        — confirmacao sem link salvo")
        self.stdout.write("  [com_link]           Bruno Com Link        — link salvo, nao confirmado")
        self.stdout.write("  [ligacao_confirmada] Carla Ligacao Ok      — ligacao confirmada, averbacao pendente")
        self.stdout.write("  [completo_atual]     Diego Completo        — ligacao e averbacao confirmadas")
        self.stdout.write("  [historico_1]        Eduarda Historico     — mes anterior confirmado, atual com link")
        self.stdout.write("  [historico_2]        Felipe Multiplo       — 3 competencias, 2 confirmadas")
        self.stdout.write("  [pendenciado]        Giovana Pendenciada   — contrato congelado na tesouraria")
        self.stdout.write("  [pag_pix]            Henrique Pago Pix     — pagamento pago via PIX")
        self.stdout.write("  [pag_ted]            Isabela Paga Ted      — pagamento pago via TED")
        self.stdout.write("  [pag_pendente]       Jonas Pag Pendente    — pagamento pendente")
        self.stdout.write("  [pag_cancelado]      Larissa Pag Cancelado — pagamento cancelado")
        self.stdout.write("  [multi_comp]         Marcos Multi Comp     — dois pagamentos em ciclos distintos")
        self.stdout.write("")
        self.stdout.write(f"Totais:")
        self.stdout.write(f"  Associados:   {n_assoc}")
        self.stdout.write(f"  Contratos:    {n_contratos}")
        self.stdout.write(f"  Confirmacoes: {n_confirmacoes}")
        self.stdout.write(f"  Pagamentos:   {n_pagamentos}")
