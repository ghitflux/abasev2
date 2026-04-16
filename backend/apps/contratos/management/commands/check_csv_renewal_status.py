"""
Verifica o status de renovação dos associados da planilha "Passível de Renovação - Abril/26".

Cruza os CPFs da lista com:
1. Refinanciamento: quem já tem renovação efetivada ou em andamento na tesouraria
2. Contrato: quem ainda aparece como apto_a_renovar sem fluxo ativo

Uso:
  python manage.py check_csv_renewal_status
  python manage.py check_csv_renewal_status --format=csv
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.contratos.cycle_projection import resolve_cycle_visual_status
from apps.contratos.models import Ciclo, Contrato
from apps.refinanciamento.models import Refinanciamento

CSV_CPFS = [
    ("20168942372", "MARIA DO SOCORRO RUBEN PEREIRA", "007638-4"),
    ("23993596315", "MARIA DE JESUS SANTANA COSTA", "030759-9"),
    ("22808922353", "JOAQUIM VIEIRA FILHO", "002802-9"),
    ("22796843300", "GILMAR DE DEUS LIMA", "002805-3"),
    ("23985895368", "ROBERTO WILIAM NEGREIROS DE SO", "002827-4"),
    ("34781544304", "JOSELINO MOREIRA DA SILVA", "003114-3"),
    ("44183054400", "FRANCISCO JOSE DE SALES FILHO", "038012-1"),
    ("19941447349", "REGIS SOARES SANTOS", "038649-9"),
    ("32747519368", "ADEVANDRO DE BRITO SILVA", "039299-5"),
    ("32784066304", "FRANCISCO JORGE DA SILVA", "042583-4"),
    ("37211420120", "VALMIR DE ALBUQUERQUE PAULINO", "044927-0"),
    ("30513367349", "SILVIO MARIO PAZ LANDIN SENA", "001099-5"),
    ("34768807372", "MARIA DO ROSARIO DE FATIMA MAC", "004004-5"),
    ("41233875353", "MARIA DE LOURDES PEREIRA DOS S", "014725-7"),
    ("34801383300", "FRANCINEIDE NASCIMENTO SILVA", "018993-6"),
    ("21819424391", "FRANCISCO CRISOSTOMO BATISTA", "019061-6"),
    ("26713462391", "CARLOS EUGENIO ALVES LEAL", "019315-1"),
    ("37112147115", "JOAO FERREIRA SIMAO", "019337-2"),
    ("28784197315", "MARIA SOLANGE HOLANDA DA SILVA", "021108-7"),
    ("28699300387", "EDSON MARTINS DA SILVA", "021625-9"),
    ("41168755387", "JOEDI GALVAO DIAS", "036099-6"),
    ("28740602320", "MARIA DA GUIA MARTINS", "036839-3"),
    ("28765079353", "FRANCISCA MARIA OLIVEIRA CUNHA", "038780-X"),
    ("23989599372", "PAULO FRANCISCO DOS SANTOS", "041310-X"),
    ("33889716334", "HERCLES DOUGLAS DE SOUSA", "013605-X"),
    ("33947597304", "JOSINEA SOARES MARTINS", "001420-6"),
    ("43971636349", "CLAUDIA MARIA DE SOUSA", "009435-8"),
    ("27445682368", "JOSE AURIMAR DA SILVA", "009533-8"),
    ("69199710382", "ANA CELIA SOBRAL MOURA DE OLIV", "009598-2"),
    ("30704197391", "JOAQUIM EVANGELISTA DE SOUSA B", "013292-6"),
    ("34159983391", "LUIZ CARLOS RIBEIRO DE ARAUJO", "013691-3"),
    ("35010355353", "ANTONIO JOSE LOPES DA COSTA", "013822-3"),
    ("34931066372", "PEDRO RODRIGUES DOS SANTOS", "014058-9"),
    ("42105196349", "MARCOS ANTONIO PLACIDO DA SILV", "014845-8"),
    ("39483029368", "CARLOS ALBERTO DOS SANTOS CARD", "015270-6"),
    ("47895357387", "MAURO PEREIRA DA SILVA", "015383-4"),
    ("48149233334", "VALDIR GONZAGA MARTINS", "015860-7"),
    ("38653621334", "ROBERTO CARLOS NOGUEIRA DE ARA", "015972-7"),
    ("52438201134", "CLAUDIOMAR SOARES DE LIMA", "016142-0"),
    ("53498461320", "MARIA DO SOCORRO FERREIRA DE C", "047500-9"),
    ("13852540330", "LAUDECY MARIA DE MORAIS FERREI", "016376-7"),
    ("73879282820", "JOSE CAMPELO DA SILVA", "016399-6"),
    ("62975895348", "LUIZ GONZAGA DE SOUSA", "016502-6"),
    ("22730281304", "RAIMUNDO GONZAGA DA SILVA", "016523-9"),
    ("27373630391", "PAULO DAMASCENO GOMES FILHO", "016575-1"),
    ("28758943315", "MARIA LUCIA DA SILVA", "023879-1"),
    ("24053198372", "ANA MARIA DAS DORES SOARES", "017695-8"),
    ("19909454300", "MARIA DO SOCORRO SANTOS SILVEI", "027929-3"),
    ("13889214304", "MARIA DALVA PEREIRA DA SILVA", "028713-0"),
    ("10529560330", "JOSE FRANCISCO RIBEIRO DE SOUS", "024310-8"),
    ("23951630310", "PAULO HENRIQUE DA SILVA", "030310-X"),
    ("37517520300", "JOAO DE JESUS OLIVEIRA", "030418-2"),
    ("30593573315", "JORDIVAL GOMES DA SILVA", "030468-9"),
    ("20111916372", "MARLUCE SILVA BARROS", "030558-8"),
    ("13131010363", "MARIA ALICE ALVES DA COSTA", "036527-X"),
    ("20034431349", "RITA LINDALVA ALVES DE OLIVEIR", "002549-6"),
    ("9683771300", "VERBERT EDUARDO VERAS LIMA", "002851-7"),
    ("43932711300", "MARIA DA CONCEICAO CARVALHO CA", "003250-6"),
    ("7893515368", "RITA CECILIA GONDIM VERAS", "004365-6"),
    ("15630013300", "GRACA DE MARIA RIBEIRO MENDES", "005006-7"),
    ("48717231787", "MAMEDE RODRIGUES CARDOSO VIEIR", "009056-5"),
    ("4705033353", "DEOCLECIO FRANCISCO DE ARAUJO", "009803-5"),
    ("4732243304", "FRANCISCO ARAUJO DA SILVEIRA", "010060-9"),
    ("4511018391", "JOSELIO TALEIRES", "010062-5"),
    ("4710975353", "FRANCISCO MORAIS DOS SANTOS", "011454-5"),
    ("13201280330", "RAIMUNDO NONATO DE ARAUJO", "011727-7"),
    ("21739650344", "ANTONIO HOLANDA DA SILVA FILHO", "011918-X"),
    ("22623485372", "FRANCISCO ALVES DA SILVA", "011927-0"),
    ("15633322304", "ANTONIO FERREIRA DA SILVA", "011978-4"),
    ("35108010320", "GILBERTO SOUSA", "013276-4"),
    ("19279841300", "JOSE AMERICO DE OLIVEIRA", "013326-4"),
    ("34264060397", "DOURIVAL GOMES DA SILVA", "014144-5"),
    ("33724938349", "MARIA ELIZETE DE ANDRADE SILVA", "014283-2"),
    ("30632579315", "EDMAR SILVA FRAZ", "014457-6"),
    ("15221245353", "RITA MARIA MENDES DA SILVA", "014772-9"),
    ("42858658315", "ANTONIO JOAQUIM BRANDAO", "014856-3"),
    ("37269542368", "MARCOS ANTONIO VAZ DE BARROS", "014930-6"),
    ("42863163353", "DAMIAO DE OLIVEIRA GOMES", "015093-2"),
    ("37508733304", "RAIMUNDO NONATO ARAUJO BARROS", "015299-4"),
    ("45130051300", "FRANCISCO LUIS FERREIRA", "015542-0"),
    ("45125260304", "JUSTINO DA SILVA LEAL", "015547-X"),
    ("13028430363", "VERA LUCIA DE FATIMA LOPES", "018295-8"),
    ("33731411334", "RAIMUNDA ALMEIDA DE ARAUJO MEL", "021091-9"),
    ("10616985304", "FRANCISCA DAS CHAGAS DE OLIVEI", "021833-2"),
    ("15639754320", "SONIA MARIA COSTA LIMA DE FREI", "035844-4"),
    ("29368669368", "LUIS DUARTE DE SOUZA", "042706-3"),
    ("28675568304", "MARIA LUSINETE SILVA SANTOS", "042879-5"),
    ("3442333830", "ANTONIO PEREIRA DE MORAIS", "043133-8"),
    ("11225858372", "MARIA NAIR RIBEIRO DA SILVA SA", "043718-2"),
    ("15221318334", "FIRMINO DE SOUSA E SILVA", "025043-X"),
    ("15146820368", "MARIA SALOME RABELO", "048574-8"),
    ("93574177453", "VIRGINIA MARIA LIMA MATOS DE C", "050682-6"),
    ("13019414334", "MARIA DO PERPETUO SOCORRO VASC", "051174-9"),
    ("7883684353", "EDVALDO DA CUNHA COSTA", "051269-9"),
    ("6541062315", "MARIA LUIZA MUNIZ GUIMARAES", "052747-5"),
    ("3028801353", "MARIA DAS GRACAS PORTELA VELOS", "053362-9"),
    ("15119998372", "ELIANE MARIA MENDES DOS SANTOS", "054098-6"),
    ("40375552472", "MARIA DE LOURDES DA SILVA", "054977-X"),
]


REFINANCIAMENTO_STATUS_LABELS = {
    "apto_a_renovar": "Apto a renovar",
    "pendente_apto": "Pendente apto",
    "solicitado": "Solicitado",
    "em_analise": "Em análise",
    "em_analise_renovacao": "Em análise (renovação)",
    "pendente_termo_analista": "Pendente termo analista",
    "pendente_termo_agente": "Pendente termo agente",
    "aprovado_analise_renovacao": "Aprovado análise",
    "aprovado_para_renovacao": "Aprovado p/ tesouraria",
    "efetivado": "EFETIVADO",
    "bloqueado": "Bloqueado",
    "revertido": "Revertido",
    "desativado": "Desativado",
    "concluido": "Concluído",
}

# Statuses considerados como "já renovado" para efeito desta análise
RENOVADO_STATUSES = {"efetivado", "concluido"}

# Statuses em fluxo ativo (ainda em andamento)
FLUXO_ATIVO_STATUSES = {
    "solicitado", "em_analise", "em_analise_renovacao",
    "pendente_termo_analista", "pendente_termo_agente",
    "aprovado_analise_renovacao", "aprovado_para_renovacao",
    "pendente_apto",
}


class Command(BaseCommand):
    help = "Verifica status de renovação dos associados da planilha Passível de Renovação - Abril/26"

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=["table", "csv"],
            default="table",
            help="Formato de saída (table ou csv)",
        )
        parser.add_argument(
            "--apenas-pendentes",
            action="store_true",
            default=False,
            help="Mostra apenas quem ainda NÃO foi renovado",
        )

    def handle(self, *args, **options):
        output_format = options["format"]
        apenas_pendentes = options["apenas_pendentes"]

        all_cpfs = [row[0] for row in CSV_CPFS]

        # Busca o refinanciamento mais recente por CPF (competência 2026)
        refinanciamentos = (
            Refinanciamento.objects.select_related("associado", "contrato_origem")
            .filter(
                associado__cpf_cnpj__in=all_cpfs,
                deleted_at__isnull=True,
                competencia_solicitada__year=2026,
            )
            .order_by("-created_at")
        )
        refin_by_cpf: dict[str, list[Refinanciamento]] = {}
        for r in refinanciamentos:
            cpf = r.associado.cpf_cnpj
            refin_by_cpf.setdefault(cpf, []).append(r)

        # Busca contratos apto_a_renovar (ciclos ou status no contrato)
        contratos_ativos = (
            Contrato.objects.select_related("associado")
            .filter(
                associado__cpf_cnpj__in=all_cpfs,
                status=Contrato.Status.ATIVO,
                deleted_at__isnull=True,
            )
            .prefetch_related("ciclos")
        )
        contrato_by_cpf: dict[str, list[Contrato]] = {}
        for c in contratos_ativos:
            cpf = c.associado.cpf_cnpj
            contrato_by_cpf.setdefault(cpf, []).append(c)

        results = []

        for cpf, nome, matricula in CSV_CPFS:
            refins = refin_by_cpf.get(cpf, [])
            contratos = contrato_by_cpf.get(cpf, [])

            # Determina o status consolidado
            if refins:
                latest = refins[0]
                status_code = latest.status
                status_label = REFINANCIAMENTO_STATUS_LABELS.get(status_code, status_code)
                competencia = str(latest.competencia_solicitada) if latest.competencia_solicitada else "—"
                grupo = (
                    "RENOVADO" if status_code in RENOVADO_STATUSES
                    else "EM_FLUXO" if status_code in FLUXO_ATIVO_STATUSES
                    else "BLOQUEADO"
                )
            else:
                # Sem refinanciamento em 2026 — verifica ciclos ativos
                status_label = "Sem renovação iniciada"
                competencia = "—"
                has_apto = False
                for contrato in contratos:
                    for ciclo in contrato.ciclos.filter(deleted_at__isnull=True).order_by("-numero"):
                        if ciclo.status in ("apto_a_renovar",):
                            has_apto = True
                            break
                    if has_apto:
                        break
                grupo = "APTO_SEM_FLUXO" if has_apto else "SEM_DADOS"

            row = {
                "cpf": cpf,
                "nome": nome[:30],
                "matricula": matricula,
                "grupo": grupo,
                "status": status_label,
                "competencia_2026": competencia,
                "total_refins_2026": len(refins),
            }
            results.append(row)

        if apenas_pendentes:
            results = [r for r in results if r["grupo"] != "RENOVADO"]

        # Sumário
        grupos = {}
        for r in results:
            grupos[r["grupo"]] = grupos.get(r["grupo"], 0) + 1

        if output_format == "csv":
            self._print_csv(results, grupos)
        else:
            self._print_table(results, grupos)

    def _print_table(self, results, grupos):
        self.stdout.write("\n" + "=" * 100)
        self.stdout.write("  VERIFICAÇÃO CSV - PASSÍVEL DE RENOVAÇÃO ABRIL/26")
        self.stdout.write("=" * 100)

        legenda = {
            "RENOVADO": self.style.SUCCESS("RENOVADO"),
            "EM_FLUXO": self.style.WARNING("EM FLUXO"),
            "BLOQUEADO": self.style.ERROR("BLOQUEADO"),
            "APTO_SEM_FLUXO": self.style.WARNING("APTO SEM FLUXO"),
            "SEM_DADOS": "SEM DADOS",
        }

        header = f"{'CPF':<14} {'NOME':<32} {'MATRÍCULA':<12} {'GRUPO':<16} {'STATUS':<30} {'COMP':<10} {'#REFINS'}"
        self.stdout.write(header)
        self.stdout.write("-" * 110)

        for r in results:
            grupo_label = legenda.get(r["grupo"], r["grupo"])
            line = (
                f"{r['cpf']:<14} {r['nome']:<32} {r['matricula']:<12} "
                f"{r['grupo']:<16} {r['status']:<30} {r['competencia_2026']:<10} {r['total_refins_2026']}"
            )
            self.stdout.write(line)

        self.stdout.write("\n" + "=" * 100)
        self.stdout.write("  SUMÁRIO")
        self.stdout.write("=" * 100)
        total = sum(grupos.values())
        for grupo, count in sorted(grupos.items()):
            pct = count / total * 100
            self.stdout.write(f"  {grupo:<20} {count:>4} ({pct:.1f}%)")
        self.stdout.write(f"  {'TOTAL':<20} {total:>4}")
        self.stdout.write("=" * 100 + "\n")

    def _print_csv(self, results, grupos):
        self.stdout.write("cpf,nome,matricula,grupo,status,competencia_2026,total_refins_2026")
        for r in results:
            self.stdout.write(
                f"{r['cpf']},{r['nome']},{r['matricula']},{r['grupo']},"
                f"{r['status']},{r['competencia_2026']},{r['total_refins_2026']}"
            )
        self.stdout.write("\n# SUMÁRIO")
        for grupo, count in sorted(grupos.items()):
            self.stdout.write(f"# {grupo}: {count}")
