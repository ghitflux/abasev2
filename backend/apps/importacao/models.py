from django.conf import settings
from django.db import models

from core.models import BaseModel


class PagamentoMensalidade(BaseModel):
    """Registro de pagamento de mensalidade importado do arquivo retorno (pagamentos_mensalidades)."""

    class ManualStatus(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        PAGO = "pago", "Pago"
        CANCELADO = "cancelado", "Cancelado"

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pagamentos_mensalidades_criados",
    )
    import_uuid = models.CharField(max_length=36)
    referencia_month = models.DateField()
    status_code = models.CharField(max_length=2, blank=True)
    matricula = models.CharField(max_length=40, blank=True)
    orgao_pagto = models.CharField(max_length=40, blank=True)
    nome_relatorio = models.CharField(max_length=200, blank=True)
    cpf_cnpj = models.CharField(max_length=20)
    associado = models.ForeignKey(
        "associados.Associado",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pagamentos_mensalidades",
    )
    valor = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    esperado_manual = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    recebido_manual = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    manual_status = models.CharField(
        max_length=20, choices=ManualStatus.choices, null=True, blank=True
    )
    agente_refi_solicitado = models.BooleanField(default=False)
    manual_paid_at = models.DateTimeField(null=True, blank=True)
    manual_forma_pagamento = models.CharField(max_length=40, blank=True)
    manual_comprovante_path = models.CharField(max_length=500, blank=True)
    manual_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pagamentos_mensalidades_manuais",
    )
    source_file_path = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-referencia_month", "cpf_cnpj"]
        indexes = [
            models.Index(fields=["cpf_cnpj", "referencia_month"]),
            models.Index(fields=["import_uuid"]),
        ]

    def __str__(self) -> str:
        return f"PagMensalidade {self.cpf_cnpj} {self.referencia_month}"


class ArquivoRetorno(BaseModel):
    class Formato(models.TextChoices):
        TXT = "txt", "TXT"
        CSV = "csv", "CSV"
        XLSX = "xlsx", "XLSX"
        MANUAL = "man", "Manual"

    class Status(models.TextChoices):
        AGUARDANDO_CONFIRMACAO = "aguardando_confirmacao", "Aguardando Confirmação"
        PENDENTE = "pendente", "Pendente"
        PROCESSANDO = "processando", "Processando"
        CONCLUIDO = "concluido", "Concluído"
        ERRO = "erro", "Erro"

    arquivo_nome = models.CharField(max_length=255)
    arquivo_url = models.TextField()
    formato = models.CharField(max_length=4, choices=Formato.choices)
    orgao_origem = models.CharField(max_length=100)
    competencia = models.DateField()
    total_registros = models.PositiveIntegerField(default=0)
    processados = models.PositiveIntegerField(default=0)
    nao_encontrados = models.PositiveIntegerField(default=0)
    erros = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.PENDENTE
    )
    resultado_resumo = models.JSONField(default=dict, blank=True)
    dry_run_resultado = models.JSONField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="arquivos_retorno",
    )
    processado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class ArquivoRetornoItem(BaseModel):
    class StatusDesconto(models.TextChoices):
        EFETIVADO = "efetivado", "Efetivado"
        REJEITADO = "rejeitado", "Rejeitado"
        CANCELADO = "cancelado", "Cancelado"
        PENDENTE = "pendente", "Pendente"

    class ResultadoProcessamento(models.TextChoices):
        BAIXA_EFETUADA = "baixa_efetuada", "Baixa efetuada"
        NAO_DESCONTADO = "nao_descontado", "Não descontado"
        PENDENCIA_MANUAL = "pendencia_manual", "Pendência manual"
        DUPLICIDADE = "duplicidade", "Duplicidade"
        NAO_ENCONTRADO = "nao_encontrado", "Não encontrado"
        ERRO = "erro", "Erro"
        CICLO_ABERTO = "ciclo_aberto", "Ciclo aberto"

    arquivo_retorno = models.ForeignKey(
        ArquivoRetorno, on_delete=models.CASCADE, related_name="itens"
    )
    linha_numero = models.PositiveIntegerField()
    cpf_cnpj = models.CharField(max_length=18)
    matricula_servidor = models.CharField(max_length=50)
    nome_servidor = models.CharField(max_length=255)
    cargo = models.CharField(max_length=255, blank=True)
    competencia = models.CharField(max_length=7)
    valor_descontado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status_codigo = models.CharField(max_length=1, blank=True)
    status_desconto = models.CharField(
        max_length=20, choices=StatusDesconto.choices, default=StatusDesconto.PENDENTE
    )
    status_descricao = models.CharField(max_length=255, blank=True)
    motivo_rejeicao = models.TextField(null=True, blank=True)
    orgao_codigo = models.CharField(max_length=10, blank=True)
    orgao_pagto_codigo = models.CharField(max_length=10, blank=True)
    orgao_pagto_nome = models.CharField(max_length=255, blank=True)
    associado = models.ForeignKey(
        "associados.Associado",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="itens_retorno",
    )
    parcela = models.ForeignKey(
        "contratos.Parcela",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="itens_retorno",
    )
    processado = models.BooleanField(default=False)
    resultado_processamento = models.CharField(
        max_length=30,
        choices=ResultadoProcessamento.choices,
        default=ResultadoProcessamento.CICLO_ABERTO,
    )
    observacao = models.TextField(blank=True)
    payload_bruto = models.JSONField(default=dict, blank=True)
    gerou_encerramento = models.BooleanField(default=False)
    gerou_novo_ciclo = models.BooleanField(default=False)

    class Meta:
        ordering = ["linha_numero"]


class DuplicidadeFinanceira(BaseModel):
    class Status(models.TextChoices):
        ABERTA = "aberta", "Aberta"
        EM_TRATAMENTO = "em_tratamento", "Em tratamento"
        RESOLVIDA = "resolvida", "Resolvida"
        DESCARTADA = "descartada", "Descartada"

    class Motivo(models.TextChoices):
        BAIXA_MANUAL_DUPLICADA = (
            "baixa_manual_duplicada",
            "Baixa manual duplicada",
        )
        BAIXA_MANUAL_MES_ERRADO = (
            "baixa_manual_mes_errado",
            "Baixa manual em mês errado",
        )
        DIVERGENCIA_VALOR = "divergencia_valor", "Divergência de valor"
        CONFLITO_RETORNO = "conflito_retorno", "Conflito vindo do retorno"

    arquivo_retorno_item = models.ForeignKey(
        "importacao.ArquivoRetornoItem",
        on_delete=models.PROTECT,
        related_name="duplicidades_financeiras",
    )
    pagamento_mensalidade = models.ForeignKey(
        "importacao.PagamentoMensalidade",
        on_delete=models.PROTECT,
        related_name="duplicidades_financeiras",
        null=True,
        blank=True,
    )
    associado = models.ForeignKey(
        "associados.Associado",
        on_delete=models.PROTECT,
        related_name="duplicidades_financeiras",
        null=True,
        blank=True,
    )
    contrato = models.ForeignKey(
        "contratos.Contrato",
        on_delete=models.PROTECT,
        related_name="duplicidades_financeiras",
        null=True,
        blank=True,
    )
    motivo = models.CharField(max_length=40, choices=Motivo.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ABERTA,
    )
    competencia_retorno = models.DateField()
    competencia_manual = models.DateField(null=True, blank=True)
    valor_retorno = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    valor_manual = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    observacao = models.TextField(blank=True)
    devolucao = models.ForeignKey(
        "tesouraria.DevolucaoAssociado",
        on_delete=models.PROTECT,
        related_name="duplicidades_financeiras",
        null=True,
        blank=True,
    )
    resolvido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="duplicidades_financeiras_resolvidas",
        null=True,
        blank=True,
    )
    resolvido_em = models.DateTimeField(null=True, blank=True)
    motivo_resolucao = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "motivo"]),
            models.Index(fields=["competencia_retorno"]),
        ]

    def __str__(self) -> str:
        return f"DuplicidadeFinanceira #{self.pk} - {self.motivo}"


class ImportacaoLog(BaseModel):
    class Tipo(models.TextChoices):
        UPLOAD = "upload", "Upload"
        PARSE = "parse", "Parse"
        VALIDACAO = "validacao", "Validação"
        RECONCILIACAO = "reconciliacao", "Reconciliação"
        BAIXA = "baixa", "Baixa"
        ERRO = "erro", "Erro"

    arquivo_retorno = models.ForeignKey(
        ArquivoRetorno, on_delete=models.CASCADE, related_name="logs"
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    mensagem = models.TextField()
    dados = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
