from enum import Enum


class Permission(Enum):
    CADASTRO_CREATE = "cadastro.create"
    CADASTRO_READ_OWN = "cadastro.read_own"
    CADASTRO_READ_ALL = "cadastro.read_all"
    CADASTRO_UPDATE_OWN = "cadastro.update_own"
    CADASTRO_UPDATE_ALL = "cadastro.update_all"
    CADASTRO_DELETE = "cadastro.delete"
    CADASTRO_SUBMIT = "cadastro.submit"

    ANALISE_VIEW = "analise.view"
    ANALISE_APPROVE = "analise.approve"
    ANALISE_REJECT = "analise.reject"
    ANALISE_REQUEST_CHANGES = "analise.request_changes"

    TESOURARIA_VIEW = "tesouraria.view"
    TESOURARIA_PROCESS = "tesouraria.process"
    TESOURARIA_GENERATE_CONTRACT = "tesouraria.generate_contract"
    TESOURARIA_VALIDATE_NUVIDEO = "tesouraria.validate_nuvideo"
    TESOURARIA_SIGN = "tesouraria.sign"
    TESOURARIA_COMPLETE = "tesouraria.complete"

    RELATORIO_VIEW_OWN = "relatorio.view_own"
    RELATORIO_VIEW_ALL = "relatorio.view_all"
    RELATORIO_EXPORT = "relatorio.export"

    RENOVACAO_REQUEST = "renovacao.request"
    RENOVACAO_APPROVE = "renovacao.approve"


ROLE_PERMISSIONS = {
    "AGENTE": [
        Permission.CADASTRO_CREATE.value,
        Permission.CADASTRO_READ_OWN.value,
        Permission.CADASTRO_UPDATE_OWN.value,
        Permission.CADASTRO_SUBMIT.value,
        Permission.RENOVACAO_REQUEST.value,
        Permission.RELATORIO_VIEW_OWN.value,
    ],
    "ANALISTA": [
        Permission.CADASTRO_READ_ALL.value,
        Permission.ANALISE_VIEW.value,
        Permission.ANALISE_APPROVE.value,
        Permission.ANALISE_REJECT.value,
        Permission.ANALISE_REQUEST_CHANGES.value,
        Permission.RENOVACAO_APPROVE.value,
        Permission.RELATORIO_VIEW_ALL.value,
        Permission.RELATORIO_EXPORT.value,
    ],
    "TESOURARIA": [
        Permission.CADASTRO_READ_ALL.value,
        Permission.TESOURARIA_VIEW.value,
        Permission.TESOURARIA_PROCESS.value,
        Permission.TESOURARIA_GENERATE_CONTRACT.value,
        Permission.TESOURARIA_VALIDATE_NUVIDEO.value,
        Permission.TESOURARIA_SIGN.value,
        Permission.TESOURARIA_COMPLETE.value,
        Permission.RELATORIO_VIEW_ALL.value,
        Permission.RELATORIO_EXPORT.value,
    ],
    "DIRETORIA": [
        Permission.CADASTRO_READ_ALL.value,
        Permission.RELATORIO_VIEW_ALL.value,
        Permission.RELATORIO_EXPORT.value,
    ],
    "ADMIN": ["*"],
}
