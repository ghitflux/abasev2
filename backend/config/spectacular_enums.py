from apps.associados.models import Associado, Documento
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.esteira.models import DocIssue, EsteiraItem, Pendencia
from apps.financeiro.models import Despesa
from apps.importacao.models import ArquivoRetorno
from apps.refinanciamento.models import Comprovante, Refinanciamento
from apps.tesouraria.models import Confirmacao, DevolucaoAssociado, Pagamento


ASSOCIADO_STATUS = Associado.Status
DOCUMENTO_TIPO = Documento.Tipo
DOCUMENTO_STATUS = Documento.Status
ESTEIRA_ETAPA = EsteiraItem.Etapa
ESTEIRA_SITUACAO = EsteiraItem.Situacao
PENDENCIA_STATUS = Pendencia.Status
DOC_ISSUE_STATUS = DocIssue.Status
CONTRATO_STATUS = Contrato.Status
CICLO_STATUS = Ciclo.Status
PARCELA_STATUS = Parcela.Status
REFINANCIAMENTO_STATUS = Refinanciamento.Status
COMPROVANTE_TIPO = Comprovante.Tipo
COMPROVANTE_PAPEL = Comprovante.Papel
COMPROVANTE_ORIGEM = Comprovante.Origem
COMPROVANTE_STATUS_VALIDACAO = Comprovante.StatusValidacao
DEVOLUCAO_ASSOCIADO_TIPO = DevolucaoAssociado.Tipo
CONFIRMACAO_TIPO = Confirmacao.Tipo
CONFIRMACAO_STATUS = Confirmacao.Status
PAGAMENTO_STATUS = Pagamento.Status
DESPESA_STATUS = Despesa.Status
DESPESA_TIPO = Despesa.Tipo
ARQUIVO_RETORNO_STATUS = ArquivoRetorno.Status
ARQUIVO_RETORNO_FORMATO = ArquivoRetorno.Formato
