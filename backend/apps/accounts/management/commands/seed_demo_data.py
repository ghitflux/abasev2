from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.management.seed_utils import ensure_access_users
from apps.accounts.models import User
from apps.associados.models import Associado, Documento
from apps.associados.services import AssociadoService
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.esteira.models import EsteiraItem, Pendencia, Transicao
from apps.esteira.services import EsteiraService
from apps.importacao.models import (
    ArquivoRetorno,
    ArquivoRetornoItem,
    ImportacaoLog,
    PagamentoMensalidade,
)
from apps.refinanciamento.models import Comprovante, Refinanciamento
from apps.refinanciamento.services import RefinanciamentoService
from apps.relatorios.models import RelatorioGerado
from apps.relatorios.services import RelatorioService
from apps.tesouraria.models import Confirmacao
from apps.tesouraria.services import ConfirmacaoService, TesourariaService

SEED_CPFS = [
    "90000000001",
    "90000000002",
    "90000000003",
    "90000000004",
    "90000000005",
    "90000000006",
    "90000000007",
    "90000000008",
    "90000000009",
    "90000000010",
    "90000000011",
    "90000000012",
]

SEED_IMPORT_PREFIX = "seed_demo_retorno_"
SEED_REPORT_PREFIX = "seed_demo_"


def add_months(base_date: date, months: int) -> date:
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


class Command(BaseCommand):
    help = "Cria usuarios base e um conjunto completo de dados demo para toda a aplicacao."

    @transaction.atomic
    def handle(self, *args, **options):
        user_specs = ensure_access_users()
        users = {
            role_code: User.objects.get(email=spec.email)
            for role_code, spec in user_specs.items()
        }
        self._seed_users = users

        self._cleanup_existing_seed()

        competencia_atual = timezone.localdate().replace(day=1)
        competencia_anterior = add_months(competencia_atual, -1)
        primeira_competencia_atual = add_months(competencia_atual, -2)
        primeira_competencia_anterior = add_months(competencia_atual, -3)

        cenarios: dict[str, dict[str, object]] = {}

        cenarios["analise"] = self._criar_associado_base(
            slug="analise",
            nome="Ana Analise",
            cpf="90000000001",
            agente=users["AGENTE"],
            primeira_mensalidade=add_months(competencia_atual, 1),
            mensalidade=Decimal("420.00"),
        )

        cenarios["pendencia"] = self._criar_associado_base(
            slug="pendencia",
            nome="Bruno Pendencia",
            cpf="90000000002",
            agente=users["AGENTE"],
            primeira_mensalidade=add_months(competencia_atual, 1),
            mensalidade=Decimal("410.00"),
        )
        EsteiraService.assumir(cenarios["pendencia"]["esteira"], users["ANALISTA"])
        EsteiraService.pendenciar(
            cenarios["pendencia"]["esteira"],
            users["ANALISTA"],
            "documentacao",
            "Documento complementar pendente no seed demo.",
        )
        cenarios["pendencia"]["associado"].documentos.update(status=Documento.Status.REJEITADO)

        cenarios["coordenacao"] = self._criar_associado_base(
            slug="coordenacao",
            nome="Carla Coordenacao",
            cpf="90000000003",
            agente=users["AGENTE"],
            primeira_mensalidade=add_months(competencia_atual, 1),
            mensalidade=Decimal("430.00"),
        )
        self._aprovar_analise(cenarios["coordenacao"]["esteira"], users["ANALISTA"])
        cenarios["coordenacao"]["associado"].documentos.update(status=Documento.Status.APROVADO)

        cenarios["tesouraria"] = self._criar_associado_base(
            slug="tesouraria",
            nome="Diego Tesouraria",
            cpf="90000000004",
            agente=users["AGENTE"],
            primeira_mensalidade=add_months(competencia_atual, 1),
            mensalidade=Decimal("440.00"),
        )
        self._levar_para_tesouraria(cenarios["tesouraria"]["esteira"], users["ANALISTA"], users["COORDENADOR"])
        cenarios["tesouraria"]["associado"].documentos.update(status=Documento.Status.APROVADO)

        cenarios["ativo"] = self._criar_associado_base(
            slug="ativo",
            nome="Elisa Ativa",
            cpf="90000000005",
            agente=users["AGENTE"],
            primeira_mensalidade=primeira_competencia_atual,
            mensalidade=Decimal("450.00"),
        )
        self._levar_para_tesouraria(cenarios["ativo"]["esteira"], users["ANALISTA"], users["COORDENADOR"])
        self._efetivar_contrato(cenarios["ativo"]["contrato"], users["TESOUREIRO"], "ativo")
        self._atualizar_parcelas(
            cenarios["ativo"]["contrato"],
            [
                (Parcela.Status.DESCONTADO, add_months(competencia_atual, -2) + timedelta(days=14), ""),
                (Parcela.Status.DESCONTADO, add_months(competencia_atual, -1) + timedelta(days=14), ""),
                (Parcela.Status.EM_ABERTO, None, "Aguardando baixa da competencia atual."),
            ],
        )

        cenarios["apto_refi"] = self._criar_associado_base(
            slug="apto_refi",
            nome="Fabio Elegivel",
            cpf="90000000006",
            agente=users["AGENTE"],
            primeira_mensalidade=primeira_competencia_atual,
            mensalidade=Decimal("460.00"),
        )
        self._levar_para_tesouraria(cenarios["apto_refi"]["esteira"], users["ANALISTA"], users["COORDENADOR"])
        self._efetivar_contrato(cenarios["apto_refi"]["contrato"], users["TESOUREIRO"], "apto_refi")
        self._marcar_todas_parcelas_pagas(cenarios["apto_refi"]["contrato"], competencia_atual + timedelta(days=4))

        cenarios["refi_pendente"] = self._criar_associado_base(
            slug="refi_pendente",
            nome="Gabriela Refinanciamento",
            cpf="90000000007",
            agente=users["AGENTE"],
            primeira_mensalidade=primeira_competencia_atual,
            mensalidade=Decimal("470.00"),
        )
        self._levar_para_tesouraria(cenarios["refi_pendente"]["esteira"], users["ANALISTA"], users["COORDENADOR"])
        self._efetivar_contrato(cenarios["refi_pendente"]["contrato"], users["TESOUREIRO"], "refi_pendente")
        self._marcar_todas_parcelas_pagas(cenarios["refi_pendente"]["contrato"], competencia_atual + timedelta(days=5))
        cenarios["refi_pendente"]["refinanciamento"] = RefinanciamentoService.solicitar(
            cenarios["refi_pendente"]["contrato"].id,
            users["AGENTE"],
        )

        cenarios["refi_bloqueado"] = self._criar_associado_base(
            slug="refi_bloqueado",
            nome="Helena Bloqueada",
            cpf="90000000008",
            agente=users["AGENTE"],
            primeira_mensalidade=primeira_competencia_atual,
            mensalidade=Decimal("480.00"),
        )
        self._levar_para_tesouraria(cenarios["refi_bloqueado"]["esteira"], users["ANALISTA"], users["COORDENADOR"])
        self._efetivar_contrato(cenarios["refi_bloqueado"]["contrato"], users["TESOUREIRO"], "refi_bloqueado")
        self._marcar_todas_parcelas_pagas(cenarios["refi_bloqueado"]["contrato"], competencia_atual + timedelta(days=6))
        refinanciamento_bloqueado = RefinanciamentoService.solicitar(
            cenarios["refi_bloqueado"]["contrato"].id,
            users["AGENTE"],
        )
        cenarios["refi_bloqueado"]["refinanciamento"] = RefinanciamentoService.bloquear(
            refinanciamento_bloqueado.id,
            "Bloqueio manual de exemplo para o seed demo.",
            users["COORDENADOR"],
        )

        cenarios["refi_efetivado"] = self._criar_associado_base(
            slug="refi_efetivado",
            nome="Igor Efetivado",
            cpf="90000000009",
            agente=users["AGENTE"],
            primeira_mensalidade=primeira_competencia_atual,
            mensalidade=Decimal("490.00"),
        )
        self._levar_para_tesouraria(cenarios["refi_efetivado"]["esteira"], users["ANALISTA"], users["COORDENADOR"])
        self._efetivar_contrato(cenarios["refi_efetivado"]["contrato"], users["TESOUREIRO"], "refi_efetivado")
        self._marcar_todas_parcelas_pagas(cenarios["refi_efetivado"]["contrato"], competencia_atual + timedelta(days=7))
        refinanciamento_efetivado = RefinanciamentoService.solicitar(
            cenarios["refi_efetivado"]["contrato"].id,
            users["AGENTE"],
        )
        refinanciamento_efetivado = RefinanciamentoService.aprovar(
            refinanciamento_efetivado.id,
            users["COORDENADOR"],
        )
        cenarios["refi_efetivado"]["refinanciamento"] = RefinanciamentoService.efetivar(
            refinanciamento_efetivado.id,
            self._arquivo_upload("refi_efetivado_associado.pdf", b"seed refinanciamento associado"),
            self._arquivo_upload("refi_efetivado_agente.pdf", b"seed refinanciamento agente"),
            users["TESOUREIRO"],
        )

        cenarios["inadimplente"] = self._criar_associado_base(
            slug="inadimplente",
            nome="Julia Inadimplente",
            cpf="90000000010",
            agente=users["AGENTE"],
            primeira_mensalidade=primeira_competencia_atual,
            mensalidade=Decimal("500.00"),
        )
        self._levar_para_tesouraria(cenarios["inadimplente"]["esteira"], users["ANALISTA"], users["COORDENADOR"])
        self._efetivar_contrato(cenarios["inadimplente"]["contrato"], users["TESOUREIRO"], "inadimplente")
        self._atualizar_parcelas(
            cenarios["inadimplente"]["contrato"],
            [
                (Parcela.Status.DESCONTADO, add_months(competencia_atual, -2) + timedelta(days=12), ""),
                (Parcela.Status.DESCONTADO, add_months(competencia_atual, -1) + timedelta(days=12), ""),
                (Parcela.Status.NAO_DESCONTADO, None, "Parcela retornou sem desconto."),
            ],
        )
        cenarios["inadimplente"]["associado"].status = Associado.Status.INADIMPLENTE
        cenarios["inadimplente"]["associado"].save(update_fields=["status", "updated_at"])

        cenarios["ciclo_renovado"] = self._criar_associado_base(
            slug="ciclo_renovado",
            nome="Kelly Renovada",
            cpf="90000000011",
            agente=users["AGENTE"],
            primeira_mensalidade=primeira_competencia_atual,
            mensalidade=Decimal("510.00"),
        )
        self._levar_para_tesouraria(cenarios["ciclo_renovado"]["esteira"], users["ANALISTA"], users["COORDENADOR"])
        self._efetivar_contrato(cenarios["ciclo_renovado"]["contrato"], users["TESOUREIRO"], "ciclo_renovado")
        self._marcar_todas_parcelas_pagas(cenarios["ciclo_renovado"]["contrato"], competencia_atual + timedelta(days=3))
        ciclo_renovado = cenarios["ciclo_renovado"]["contrato"].ciclos.order_by("numero").first()
        if ciclo_renovado:
            ciclo_renovado.status = Ciclo.Status.CICLO_RENOVADO
            ciclo_renovado.save(update_fields=["status", "updated_at"])
        cenarios["ciclo_renovado"]["contrato"].status = Contrato.Status.ENCERRADO
        cenarios["ciclo_renovado"]["contrato"].save(update_fields=["status", "updated_at"])

        Associado.objects.create(
            nome_completo="Lucas Inativo",
            cpf_cnpj="90000000012",
            email="lucas.inativo@seed.local",
            telefone="86999990012",
            orgao_publico="SEDUC",
            matricula_orgao="SEED-90000000012",
            status=Associado.Status.INATIVO,
            agente_responsavel=users["AGENTE"],
            observacao="Associado inativo criado pelo seed demo.",
        )

        self._seed_confirmacoes(cenarios, users["TESOUREIRO"], competencia_atual)
        self._seed_importacoes(cenarios, users["ADMIN"], competencia_atual, competencia_anterior)
        self._seed_relatorios()

        self.stdout.write(self.style.SUCCESS("Seed demo concluido com sucesso."))
        self.stdout.write("")
        self.stdout.write("Usuarios criados/atualizados:")
        for role_code, spec in user_specs.items():
            self.stdout.write(f"- {role_code}: {spec.email} / {spec.password}")

        self.stdout.write("")
        self.stdout.write("Resumo dos dados demo:")
        self.stdout.write(f"- Associados seed: {Associado.objects.filter(cpf_cnpj__in=SEED_CPFS).count()}")
        self.stdout.write(f"- Contratos seed: {Contrato.objects.filter(associado__cpf_cnpj__in=SEED_CPFS).count()}")
        self.stdout.write(f"- Refinanciamentos seed: {Refinanciamento.objects.filter(associado__cpf_cnpj__in=SEED_CPFS).count()}")
        self.stdout.write(f"- Arquivos retorno seed: {ArquivoRetorno.objects.filter(arquivo_nome__startswith=SEED_IMPORT_PREFIX).count()}")
        self.stdout.write(f"- Relatorios seed: {RelatorioGerado.objects.filter(nome__startswith=SEED_REPORT_PREFIX).count()}")

    def _cleanup_existing_seed(self):
        arquivo_ids = list(
            ArquivoRetorno.all_objects.filter(
                arquivo_nome__startswith=SEED_IMPORT_PREFIX
            ).values_list("id", flat=True)
        )
        if arquivo_ids:
            ImportacaoLog.all_objects.filter(arquivo_retorno_id__in=arquivo_ids).hard_delete()
            ArquivoRetornoItem.all_objects.filter(arquivo_retorno_id__in=arquivo_ids).hard_delete()
            ArquivoRetorno.all_objects.filter(id__in=arquivo_ids).hard_delete()

        RelatorioGerado.all_objects.filter(nome__startswith=SEED_REPORT_PREFIX).hard_delete()

        associado_ids = list(
            Associado.all_objects.filter(cpf_cnpj__in=SEED_CPFS).values_list("id", flat=True)
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

        Associado.all_objects.filter(id__in=associado_ids).hard_delete()

    def _criar_associado_base(
        self,
        *,
        slug: str,
        nome: str,
        cpf: str,
        agente: User,
        primeira_mensalidade: date,
        mensalidade: Decimal,
    ) -> dict[str, object]:
        associado = AssociadoService.criar_associado_completo(
            {
                "cpf_cnpj": cpf,
                "nome_completo": nome,
                "rg": f"RG-{cpf[-4:]}",
                "orgao_expedidor": "SSP-PI",
                "data_nascimento": date(1985, 1, 1) + timedelta(days=int(cpf[-2:])),
                "profissao": "Servidor publico",
                "estado_civil": Associado.EstadoCivil.CASADO,
                "cargo": "Analista administrativo",
                "observacao": f"Registro seed demo: {slug}.",
                "endereco": {
                    "cep": "64000000",
                    "logradouro": f"Rua Seed {slug.title()}",
                    "numero": str(int(cpf[-2:])),
                    "complemento": "",
                    "bairro": "Centro",
                    "cidade": "Teresina",
                    "uf": "PI",
                },
                "dados_bancarios": {
                    "banco": "Banco do Brasil",
                    "agencia": f"{cpf[-4:]}",
                    "conta": f"{cpf[-5:]}-0",
                    "tipo_conta": "corrente",
                    "chave_pix": f"{slug}@abase.seed",
                },
                "contato": {
                    "celular": f"8699999{cpf[-4:]}",
                    "email": f"{slug}@seed.local",
                    "orgao_publico": "SEFAZ",
                    "situacao_servidor": "ativo",
                    "matricula_servidor": f"SEED-{cpf[-4:]}",
                },
                "documentos_payload": [
                    {
                        "tipo": Documento.Tipo.DOCUMENTO_FRENTE,
                        "arquivo": self._arquivo_upload(f"{slug}_frente.pdf", b"documento frente"),
                    },
                    {
                        "tipo": Documento.Tipo.DOCUMENTO_VERSO,
                        "arquivo": self._arquivo_upload(f"{slug}_verso.pdf", b"documento verso"),
                    },
                    {
                        "tipo": Documento.Tipo.COMPROVANTE_RESIDENCIA,
                        "arquivo": self._arquivo_upload(f"{slug}_residencia.pdf", b"comprovante residencia"),
                    },
                ],
                "contrato": {
                    "valor_bruto_total": mensalidade * Decimal("3"),
                    "valor_liquido": mensalidade * Decimal("2.4"),
                    "prazo_meses": 3,
                    "taxa_antecipacao": Decimal("1.50"),
                    "mensalidade": mensalidade,
                    "margem_disponivel": mensalidade * Decimal("0.9"),
                    "data_aprovacao": primeira_mensalidade - timedelta(days=10),
                    "data_primeira_mensalidade": primeira_mensalidade,
                    "mes_averbacao": primeira_mensalidade,
                    "doacao_associado": Decimal("25.00"),
                },
            },
            agente,
        )
        associado.documentos.update(status=Documento.Status.PENDENTE)
        contrato = associado.contratos.order_by("-created_at").first()
        contrato.data_contrato = primeira_mensalidade - timedelta(days=15)
        contrato.save(update_fields=["data_contrato", "updated_at"])
        return {
            "associado": associado,
            "contrato": contrato,
            "esteira": associado.esteira_item,
        }

    def _aprovar_analise(self, esteira_item: EsteiraItem, analista: User):
        EsteiraService.assumir(esteira_item, analista)
        EsteiraService.aprovar(esteira_item, analista, "Aprovado na analise pelo seed demo.")

    def _levar_para_tesouraria(self, esteira_item: EsteiraItem, analista: User, coordenador: User):
        self._aprovar_analise(esteira_item, analista)

    def _efetivar_contrato(self, contrato: Contrato, tesoureiro: User, slug: str):
        TesourariaService.efetivar_contrato(
            contrato.id,
            self._arquivo_upload(f"{slug}_associado.pdf", b"comprovante associado"),
            self._arquivo_upload(f"{slug}_agente.pdf", b"comprovante agente"),
            tesoureiro,
        )
        contrato.associado.documentos.update(status=Documento.Status.APROVADO)

    def _atualizar_parcelas(self, contrato: Contrato, definicoes: list[tuple[str, date | None, str]]):
        parcelas = list(
            contrato.ciclos.order_by("numero").first().parcelas.order_by("numero")
        )
        for parcela, (status, data_pagamento, observacao) in zip(parcelas, definicoes, strict=True):
            parcela.status = status
            parcela.data_pagamento = data_pagamento
            parcela.observacao = observacao
            parcela.save(update_fields=["status", "data_pagamento", "observacao", "updated_at"])
        self._sincronizar_pagamentos_refinanciamento(contrato)

    def _marcar_todas_parcelas_pagas(self, contrato: Contrato, data_pagamento: date):
        parcelas = list(
            contrato.ciclos.order_by("numero").first().parcelas.order_by("numero")
        )
        for indice, parcela in enumerate(parcelas):
            parcela.status = Parcela.Status.DESCONTADO
            parcela.data_pagamento = data_pagamento - timedelta(days=max(2 - indice, 0) * 30)
            parcela.observacao = "Baixa seed demo."
            parcela.save(update_fields=["status", "data_pagamento", "observacao", "updated_at"])
        self._sincronizar_pagamentos_refinanciamento(contrato)

    def _sincronizar_pagamentos_refinanciamento(self, contrato: Contrato):
        parcelas = list(
            contrato.ciclos.order_by("numero").first().parcelas.order_by("numero")
        )
        referencias_pagas = {
            parcela.referencia_mes
            for parcela in parcelas
            if parcela.status == Parcela.Status.DESCONTADO
        }
        PagamentoMensalidade.objects.filter(
            associado=contrato.associado,
        ).exclude(referencia_month__in=referencias_pagas).delete()

        for parcela in parcelas:
            if parcela.status != Parcela.Status.DESCONTADO:
                continue
            PagamentoMensalidade.objects.update_or_create(
                associado=contrato.associado,
                referencia_month=parcela.referencia_mes,
                defaults={
                    "created_by": self._seed_users["TESOUREIRO"],
                    "import_uuid": f"{SEED_IMPORT_PREFIX}{contrato.id}-{parcela.referencia_mes.isoformat()}",
                    "status_code": "1",
                    "matricula": contrato.associado.matricula_orgao or contrato.associado.matricula,
                    "orgao_pagto": contrato.associado.orgao_publico,
                    "nome_relatorio": contrato.associado.nome_completo,
                    "cpf_cnpj": contrato.associado.cpf_cnpj,
                    "valor": contrato.valor_mensalidade,
                    "source_file_path": f"seed/{contrato.codigo}-{parcela.referencia_mes.isoformat()}.txt",
                },
            )

    def _seed_confirmacoes(self, cenarios: dict[str, dict[str, object]], tesoureiro: User, competencia: date):
        contrato_ativo = cenarios["ativo"]["contrato"]
        ligacao_ativo, averbacao_ativo = ConfirmacaoService._garantir_registros(
            contrato_ativo,
            competencia,
        )
        ligacao_ativo.link_chamada = "https://meet.example.com/seed-ativo"
        ligacao_ativo.save(update_fields=["link_chamada", "updated_at"])
        averbacao_ativo.observacao = "Aguardando confirmacao final."
        averbacao_ativo.save(update_fields=["observacao", "updated_at"])

        contrato_refi = cenarios["refi_efetivado"]["contrato"]
        ligacao_refi, averbacao_refi = ConfirmacaoService._garantir_registros(
            contrato_refi,
            competencia,
        )
        ligacao_refi.link_chamada = "https://meet.example.com/seed-refi"
        ligacao_refi.save(update_fields=["link_chamada", "updated_at"])
        ligacao_refi.confirmar(tesoureiro, "Ligacao confirmada pelo seed demo.")
        averbacao_refi.confirmar(tesoureiro, "Averbacao confirmada pelo seed demo.")

    def _seed_importacoes(
        self,
        cenarios: dict[str, dict[str, object]],
        admin: User,
        competencia_atual: date,
        competencia_anterior: date,
    ):
        arquivo_atual = ArquivoRetorno.objects.create(
            arquivo_nome=f"{SEED_IMPORT_PREFIX}{competencia_atual.strftime('%Y_%m')}.txt",
            arquivo_url=f"importacao/{SEED_IMPORT_PREFIX}{competencia_atual.strftime('%Y_%m')}.txt",
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="ETIPI/iNETConsig",
            competencia=competencia_atual,
            total_registros=7,
            processados=5,
            nao_encontrados=1,
            erros=1,
            status=ArquivoRetorno.Status.CONCLUIDO,
            uploaded_by=admin,
            processado_em=timezone.now(),
            resultado_resumo={
                "competencia": competencia_atual.strftime("%m/%Y"),
                "sistema_origem": "ETIPI/iNETConsig",
                "baixa_efetuada": 4,
                "nao_descontado": 1,
                "pendencias_manuais": 1,
                "nao_encontrado": 1,
                "erro": 1,
                "ciclo_aberto": 0,
                "encerramentos": 1,
                "novos_ciclos": 1,
            },
        )
        ImportacaoLog.objects.create(
            arquivo_retorno=arquivo_atual,
            tipo=ImportacaoLog.Tipo.UPLOAD,
            mensagem="Arquivo demo enviado para processamento.",
            dados={"seed": True},
        )
        ImportacaoLog.objects.create(
            arquivo_retorno=arquivo_atual,
            tipo=ImportacaoLog.Tipo.RECONCILIACAO,
            mensagem="Reconciliação demo concluída com pendências controladas.",
            dados={"seed": True},
        )

        parcelas_atuais = {
            chave: cenarios[chave]["contrato"].ciclos.order_by("numero").first().parcelas.order_by("numero").last()
            for chave in ["ativo", "apto_refi", "refi_pendente", "refi_efetivado", "inadimplente", "ciclo_renovado"]
        }

        itens_atuais = [
            self._import_item(
                arquivo_atual,
                1,
                cenarios["ativo"]["associado"],
                parcelas_atuais["ativo"],
                resultado=ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
                status_codigo="1",
                status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
                status_descricao="Baixa efetuada",
                orgao_pagto_nome="Secretaria de Educacao",
            ),
            self._import_item(
                arquivo_atual,
                2,
                cenarios["apto_refi"]["associado"],
                parcelas_atuais["apto_refi"],
                resultado=ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
                status_codigo="1",
                status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
                status_descricao="Baixa efetuada",
                orgao_pagto_nome="Secretaria de Administracao",
            ),
            self._import_item(
                arquivo_atual,
                3,
                cenarios["refi_pendente"]["associado"],
                parcelas_atuais["refi_pendente"],
                resultado=ArquivoRetornoItem.ResultadoProcessamento.PENDENCIA_MANUAL,
                status_codigo="4",
                status_desconto=ArquivoRetornoItem.StatusDesconto.PENDENTE,
                status_descricao="Pendencia manual",
                observacao="Requer conferencia manual da competencia.",
                orgao_pagto_nome="Secretaria de Saude",
            ),
            self._import_item(
                arquivo_atual,
                4,
                cenarios["refi_efetivado"]["associado"],
                parcelas_atuais["refi_efetivado"],
                resultado=ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
                status_codigo="1",
                status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
                status_descricao="Baixa efetuada",
                gerou_novo_ciclo=True,
                orgao_pagto_nome="Secretaria de Planejamento",
            ),
            self._import_item(
                arquivo_atual,
                5,
                cenarios["inadimplente"]["associado"],
                parcelas_atuais["inadimplente"],
                resultado=ArquivoRetornoItem.ResultadoProcessamento.NAO_DESCONTADO,
                status_codigo="3",
                status_desconto=ArquivoRetornoItem.StatusDesconto.REJEITADO,
                status_descricao="Nao descontado",
                motivo_rejeicao="Margem insuficiente",
                orgao_pagto_nome="Secretaria de Fazenda",
            ),
            self._import_item(
                arquivo_atual,
                6,
                cenarios["ciclo_renovado"]["associado"],
                parcelas_atuais["ciclo_renovado"],
                resultado=ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
                status_codigo="1",
                status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
                status_descricao="Baixa efetuada",
                gerou_encerramento=True,
                orgao_pagto_nome="Secretaria de Gestao",
            ),
            self._import_item(
                arquivo_atual,
                7,
                None,
                None,
                resultado=ArquivoRetornoItem.ResultadoProcessamento.NAO_ENCONTRADO,
                status_codigo="9",
                status_desconto=ArquivoRetornoItem.StatusDesconto.REJEITADO,
                status_descricao="Nao encontrado",
                motivo_rejeicao="CPF inexistente na base",
                cpf_cnpj="99999999999",
                matricula_servidor="SEED-NAO-ENCONTRADO",
                nome_servidor="Servidor nao encontrado",
                orgao_pagto_nome="Secretaria Externa",
            ),
        ]
        ArquivoRetornoItem.objects.bulk_create(itens_atuais)

        arquivo_anterior = ArquivoRetorno.objects.create(
            arquivo_nome=f"{SEED_IMPORT_PREFIX}{competencia_anterior.strftime('%Y_%m')}.txt",
            arquivo_url=f"importacao/{SEED_IMPORT_PREFIX}{competencia_anterior.strftime('%Y_%m')}.txt",
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="ETIPI/iNETConsig",
            competencia=competencia_anterior,
            total_registros=3,
            processados=3,
            nao_encontrados=0,
            erros=0,
            status=ArquivoRetorno.Status.CONCLUIDO,
            uploaded_by=admin,
            processado_em=timezone.now() - timedelta(days=25),
            resultado_resumo={
                "competencia": competencia_anterior.strftime("%m/%Y"),
                "sistema_origem": "ETIPI/iNETConsig",
                "baixa_efetuada": 3,
                "nao_descontado": 0,
                "pendencias_manuais": 0,
                "nao_encontrado": 0,
                "erro": 0,
                "ciclo_aberto": 0,
                "encerramentos": 0,
                "novos_ciclos": 0,
            },
        )
        parcelas_anteriores = {
            chave: cenarios[chave]["contrato"].ciclos.order_by("numero").first().parcelas.order_by("numero")[1]
            for chave in ["ativo", "apto_refi", "inadimplente"]
        }
        ArquivoRetornoItem.objects.bulk_create(
            [
                self._import_item(
                    arquivo_anterior,
                    1,
                    cenarios["ativo"]["associado"],
                    parcelas_anteriores["ativo"],
                    resultado=ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
                    status_codigo="1",
                    status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
                    status_descricao="Baixa efetuada",
                    orgao_pagto_nome="Secretaria de Educacao",
                ),
                self._import_item(
                    arquivo_anterior,
                    2,
                    cenarios["apto_refi"]["associado"],
                    parcelas_anteriores["apto_refi"],
                    resultado=ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
                    status_codigo="1",
                    status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
                    status_descricao="Baixa efetuada",
                    orgao_pagto_nome="Secretaria de Administracao",
                ),
                self._import_item(
                    arquivo_anterior,
                    3,
                    cenarios["inadimplente"]["associado"],
                    parcelas_anteriores["inadimplente"],
                    resultado=ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
                    status_codigo="1",
                    status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
                    status_descricao="Baixa efetuada",
                    orgao_pagto_nome="Secretaria de Fazenda",
                ),
            ]
        )

    def _import_item(
        self,
        arquivo: ArquivoRetorno,
        linha_numero: int,
        associado: Associado | None,
        parcela: Parcela | None,
        *,
        resultado: str,
        status_codigo: str,
        status_desconto: str,
        status_descricao: str,
        orgao_pagto_nome: str,
        observacao: str = "",
        motivo_rejeicao: str | None = None,
        gerou_encerramento: bool = False,
        gerou_novo_ciclo: bool = False,
        cpf_cnpj: str | None = None,
        matricula_servidor: str | None = None,
        nome_servidor: str | None = None,
    ) -> ArquivoRetornoItem:
        return ArquivoRetornoItem(
            arquivo_retorno=arquivo,
            linha_numero=linha_numero,
            cpf_cnpj=cpf_cnpj or (associado.cpf_cnpj if associado else ""),
            matricula_servidor=matricula_servidor or (associado.matricula_orgao if associado else ""),
            nome_servidor=nome_servidor or (associado.nome_completo if associado else ""),
            cargo=associado.cargo if associado else "",
            competencia=arquivo.competencia.strftime("%Y-%m"),
            valor_descontado=parcela.valor if parcela else Decimal("0.00"),
            status_codigo=status_codigo,
            status_desconto=status_desconto,
            status_descricao=status_descricao,
            motivo_rejeicao=motivo_rejeicao,
            orgao_codigo="002",
            orgao_pagto_codigo="002",
            orgao_pagto_nome=orgao_pagto_nome,
            associado=associado,
            parcela=parcela,
            processado=True,
            resultado_processamento=resultado,
            observacao=observacao,
            payload_bruto={"seed": True, "linha": linha_numero},
            gerou_encerramento=gerou_encerramento,
            gerou_novo_ciclo=gerou_novo_ciclo,
        )

    def _seed_relatorios(self):
        formatos = {
            "associados": "json",
            "tesouraria": "csv",
            "refinanciamentos": "json",
            "importacao": "csv",
        }
        for tipo, formato in formatos.items():
            rows = RelatorioService._rows_for_tipo(tipo)
            content = RelatorioService._render_content(rows, formato)
            nome = f"{SEED_REPORT_PREFIX}{tipo}.{formato}"
            relatorio = RelatorioGerado(nome=nome, formato=formato)
            relatorio.arquivo.save(
                nome,
                ContentFile(content.encode("utf-8")),
                save=False,
            )
            relatorio.save()

    def _arquivo_upload(self, nome: str, conteudo: bytes) -> SimpleUploadedFile:
        return SimpleUploadedFile(nome, conteudo, content_type="application/pdf")
