from __future__ import annotations

import re

from django.conf import settings
from django.db import models

from core.models import BaseModel


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


class Associado(BaseModel):
    class TipoDocumento(models.TextChoices):
        CPF = "CPF", "CPF"
        CNPJ = "CNPJ", "CNPJ"

    class Status(models.TextChoices):
        CADASTRADO = "cadastrado", "Cadastrado"
        EM_ANALISE = "em_analise", "Em análise"
        ATIVO = "ativo", "Ativo"
        PENDENTE = "pendente", "Pendente"
        INATIVO = "inativo", "Inativo"
        INADIMPLENTE = "inadimplente", "Inadimplente"

    class EstadoCivil(models.TextChoices):
        SOLTEIRO = "solteiro", "Solteiro"
        CASADO = "casado", "Casado"
        DIVORCIADO = "divorciado", "Divorciado"
        VIUVO = "viuvo", "Viúvo"
        UNIAO_ESTAVEL = "uniao_estavel", "União estável"

    matricula = models.CharField(max_length=20, unique=True, blank=True)
    tipo_documento = models.CharField(
        max_length=10, choices=TipoDocumento.choices, default=TipoDocumento.CPF
    )
    nome_completo = models.CharField(max_length=255)
    cpf_cnpj = models.CharField(max_length=18, unique=True)
    rg = models.CharField(max_length=30, blank=True)
    orgao_expedidor = models.CharField(max_length=80, blank=True)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=30, blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    profissao = models.CharField(max_length=120, blank=True)
    estado_civil = models.CharField(
        max_length=20, choices=EstadoCivil.choices, blank=True
    )
    orgao_publico = models.CharField(max_length=160, blank=True)
    matricula_orgao = models.CharField(max_length=60, blank=True)
    cargo = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.CADASTRADO
    )
    agente_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="associados_cadastrados",
        null=True,
        blank=True,
    )
    agente_filial = models.CharField(max_length=160, blank=True)
    auxilio_taxa = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    auxilio_status = models.CharField(max_length=80, blank=True)
    observacao = models.TextField(blank=True)

    class Meta:
        ordering = ["nome_completo"]

    def __str__(self) -> str:
        return f"{self.nome_completo} ({self.matricula or 'novo'})"

    @property
    def agente(self):
        return self.agente_responsavel

    @property
    def contato(self):
        return getattr(self, "contato_historico", None)

    @property
    def esteira(self):
        return getattr(self, "esteira_item", None)

    def save(self, *args, **kwargs):
        self.cpf_cnpj = only_digits(self.cpf_cnpj)
        if self.cpf_cnpj:
            self.tipo_documento = (
                self.TipoDocumento.CNPJ
                if len(self.cpf_cnpj) == 14
                else self.TipoDocumento.CPF
            )
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating and not self.matricula:
            self.matricula = f"MAT-{self.pk:05d}"
            super().save(update_fields=["matricula", "updated_at"])


class Endereco(BaseModel):
    associado = models.OneToOneField(
        Associado, on_delete=models.CASCADE, related_name="endereco"
    )
    cep = models.CharField(max_length=12)
    logradouro = models.CharField(max_length=255)
    numero = models.CharField(max_length=60, blank=True)
    complemento = models.CharField(max_length=120, blank=True)
    bairro = models.CharField(max_length=120)
    cidade = models.CharField(max_length=120)
    uf = models.CharField(max_length=2)

    def __str__(self) -> str:
        return f"{self.logradouro}, {self.numero or 's/n'}"


class DadosBancarios(BaseModel):
    class TipoConta(models.TextChoices):
        CORRENTE = "corrente", "Corrente"
        POUPANCA = "poupanca", "Poupança"
        SALARIO = "salario", "Salário"

    associado = models.OneToOneField(
        Associado, on_delete=models.CASCADE, related_name="dados_bancarios"
    )
    banco = models.CharField(max_length=100)
    agencia = models.CharField(max_length=20)
    conta = models.CharField(max_length=30)
    tipo_conta = models.CharField(
        max_length=20, choices=TipoConta.choices, default=TipoConta.CORRENTE
    )
    chave_pix = models.CharField(max_length=120, blank=True)

    def __str__(self) -> str:
        return f"{self.banco} - {self.agencia}/{self.conta}"


class ContatoHistorico(BaseModel):
    associado = models.OneToOneField(
        Associado, on_delete=models.CASCADE, related_name="contato_historico"
    )
    celular = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    orgao_publico = models.CharField(max_length=150, blank=True)
    situacao_servidor = models.CharField(max_length=80, blank=True)
    matricula_servidor = models.CharField(max_length=50, blank=True)
    nome_contato = models.CharField(max_length=255, blank=True)
    parentesco = models.CharField(max_length=100, blank=True)
    telefone_contato = models.CharField(max_length=20, blank=True)
    ultima_interacao_em = models.DateTimeField(null=True, blank=True)
    observacao = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.nome_contato or self.associado.nome_completo


class Documento(BaseModel):
    class Tipo(models.TextChoices):
        RG = "rg", "RG"
        CPF = "cpf", "CPF"
        DOCUMENTO_FRENTE = "documento_frente", "Documento (frente)"
        DOCUMENTO_VERSO = "documento_verso", "Documento (verso)"
        COMPROVANTE_RESIDENCIA = (
            "comprovante_residencia",
            "Comprovante de residência",
        )
        DIVULGACAO = "divulgacao", "Divulgação"
        CONTRACHEQUE = "contracheque", "Contracheque"
        TERMO_ADESAO = "termo_adesao", "Termo de adesão"
        TERMO_ANTECIPACAO = "termo_antecipacao", "Termo de antecipação"
        OUTRO = "outro", "Outro"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        APROVADO = "aprovado", "Aprovado"
        REJEITADO = "rejeitado", "Rejeitado"

    associado = models.ForeignKey(
        Associado, on_delete=models.CASCADE, related_name="documentos"
    )
    tipo = models.CharField(max_length=40, choices=Tipo.choices)
    arquivo = models.FileField(upload_to="documentos/")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDENTE
    )
    observacao = models.TextField(blank=True)

    class Meta:
        ordering = ["tipo"]

    def __str__(self) -> str:
        return f"{self.associado.nome_completo} - {self.tipo}"
