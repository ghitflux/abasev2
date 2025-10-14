from django.db import models
from django.conf import settings
from .associado import Associado


class CadastroStatus(models.TextChoices):
    RASCUNHO = "RASCUNHO"
    ENVIADO_ANALISE = "ENVIADO_ANALISE"
    PENDENTE_CORRECAO = "PENDENTE_CORRECAO"
    APROVADO_ANALISE = "APROVADO_ANALISE"
    CANCELADO = "CANCELADO"
    EM_TESOURARIA = "EM_TESOURARIA"
    AGUARDANDO_COMPROVANTES = "AGUARDANDO_COMPROVANTES"
    EM_VALIDACAO_NUVIDEO = "EM_VALIDACAO_NUVIDEO"
    CONTRATO_GERADO = "CONTRATO_GERADO"
    ASSINADO = "ASSINADO"
    CONCLUIDO = "CONCLUIDO"


class Cadastro(models.Model):
    associado = models.ForeignKey(Associado, on_delete=models.CASCADE, related_name="cadastros")
    status = models.CharField(
        max_length=32, choices=CadastroStatus.choices, default=CadastroStatus.RASCUNHO
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="cadastros_criados",
    )
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="cadastros_atualizados",
    )
    observacao = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Cadastro #{self.id} — {self.associado}"
