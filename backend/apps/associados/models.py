from __future__ import annotations

import re
from typing import Any

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.storage import default_storage
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
    cep = models.CharField(max_length=12, blank=True)
    logradouro = models.CharField(max_length=255, blank=True)
    numero = models.CharField(max_length=60, blank=True)
    complemento = models.CharField(max_length=120, blank=True)
    bairro = models.CharField(max_length=120, blank=True)
    cidade = models.CharField(max_length=120, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    orgao_publico = models.CharField(max_length=160, blank=True)
    matricula_orgao = models.CharField(max_length=60, blank=True)
    situacao_servidor = models.CharField(max_length=80, blank=True)
    banco = models.CharField(max_length=100, blank=True)
    agencia = models.CharField(max_length=20, blank=True)
    conta = models.CharField(max_length=30, blank=True)
    tipo_conta = models.CharField(max_length=20, blank=True)
    chave_pix = models.CharField(max_length=120, blank=True)
    cargo = models.CharField(max_length=120, blank=True)
    contrato_mensalidade = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    contrato_prazo_meses = models.PositiveSmallIntegerField(null=True, blank=True)
    contrato_taxa_antecipacao = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    contrato_margem_disponivel = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    contrato_data_aprovacao = models.DateField(null=True, blank=True)
    contrato_data_envio_primeira = models.DateField(null=True, blank=True)
    contrato_valor_antecipacao = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    contrato_status_contrato = models.CharField(max_length=60, blank=True)
    contrato_mes_averbacao = models.DateField(null=True, blank=True)
    contrato_codigo_contrato = models.CharField(max_length=80, blank=True)
    contrato_doacao_associado = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    calc_valor_bruto = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    calc_liquido_cc = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    calc_prazo_antecipacao = models.PositiveSmallIntegerField(null=True, blank=True)
    calc_mensalidade_associativa = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    anticipations_json = models.JSONField(null=True, blank=True)
    documents_json = models.JSONField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.CADASTRADO
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="associado",
    )
    agente_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="associados_cadastrados",
        null=True,
        blank=True,
    )
    agente_filial = models.CharField(max_length=160, blank=True)
    aceite_termos = models.BooleanField(default=False)
    termo_adesao_admin_path = models.CharField(max_length=500, blank=True)
    termo_antecipacao_admin_path = models.CharField(max_length=500, blank=True)
    contato_status = models.CharField(max_length=20, blank=True)
    contato_updated_at = models.DateTimeField(null=True, blank=True)
    auxilio1_status = models.CharField(max_length=20, blank=True)
    auxilio1_updated_at = models.DateTimeField(null=True, blank=True)
    auxilio2_status = models.CharField(max_length=20, blank=True)
    auxilio2_updated_at = models.DateTimeField(null=True, blank=True)
    auxilio_taxa = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    auxilio_data_envio = models.DateField(null=True, blank=True)
    auxilio_status = models.CharField(max_length=80, blank=True)
    observacao = models.TextField(blank=True)

    class Meta:
        ordering = ["nome_completo"]

    def __str__(self) -> str:
        return f"{self.nome_completo} ({self.matricula or 'novo'})"

    @property
    def matricula_display(self) -> str:
        contato = self._safe_related("contato_historico")
        matricula_servidor = (
            getattr(contato, "matricula_servidor", "") if contato else ""
        )
        return self.matricula_orgao or matricula_servidor or self.matricula or ""

    @property
    def agente(self):
        return self.agente_responsavel

    @property
    def contato(self):
        return self.build_contato_payload()

    @property
    def esteira(self):
        return getattr(self, "esteira_item", None)

    def _safe_related(self, attr: str):
        try:
            return getattr(self, attr)
        except ObjectDoesNotExist:
            return None

    @staticmethod
    def _has_snapshot_data(values: list[Any]) -> bool:
        return any(value not in (None, "", [], {}) for value in values)

    def build_endereco_payload(self) -> dict[str, Any] | None:
        if self._has_snapshot_data(
            [
                self.cep,
                self.logradouro,
                self.numero,
                self.complemento,
                self.bairro,
                self.cidade,
                self.uf,
            ]
        ):
            return {
                "id": None,
                "cep": self.cep,
                "endereco": self.logradouro,
                "numero": self.numero,
                "complemento": self.complemento,
                "bairro": self.bairro,
                "cidade": self.cidade,
                "uf": self.uf,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }

        endereco = self._safe_related("endereco")
        if not endereco:
            return None
        return {
            "id": endereco.id,
            "cep": endereco.cep,
            "endereco": endereco.logradouro,
            "numero": endereco.numero,
            "complemento": endereco.complemento,
            "bairro": endereco.bairro,
            "cidade": endereco.cidade,
            "uf": endereco.uf,
            "created_at": endereco.created_at,
            "updated_at": endereco.updated_at,
        }

    def build_dados_bancarios_payload(self) -> dict[str, Any] | None:
        if self._has_snapshot_data(
            [self.banco, self.agencia, self.conta, self.tipo_conta, self.chave_pix]
        ):
            return {
                "id": None,
                "associado": self.id,
                "banco": self.banco,
                "agencia": self.agencia,
                "conta": self.conta,
                "tipo_conta": self.tipo_conta,
                "chave_pix": self.chave_pix,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }

        dados_bancarios = self._safe_related("dados_bancarios")
        if not dados_bancarios:
            return None
        return {
            "id": dados_bancarios.id,
            "associado": self.id,
            "banco": dados_bancarios.banco,
            "agencia": dados_bancarios.agencia,
            "conta": dados_bancarios.conta,
            "tipo_conta": dados_bancarios.tipo_conta,
            "chave_pix": dados_bancarios.chave_pix,
            "created_at": dados_bancarios.created_at,
            "updated_at": dados_bancarios.updated_at,
        }

    def build_contato_payload(self) -> dict[str, Any] | None:
        if self._has_snapshot_data(
            [
                self.telefone,
                self.email,
                self.orgao_publico,
                self.situacao_servidor,
                self.matricula_orgao,
            ]
        ):
            return {
                "id": None,
                "associado": self.id,
                "celular": self.telefone,
                "email": self.email,
                "orgao_publico": self.orgao_publico,
                "situacao_servidor": self.situacao_servidor,
                "matricula_servidor": self.matricula_orgao,
                "nome_contato": self.nome_completo,
                "parentesco": "",
                "telefone_contato": self.telefone,
                "ultima_interacao_em": None,
                "observacao": self.observacao,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }

        contato = self._safe_related("contato_historico")
        if not contato:
            return None
        return {
            "id": contato.id,
            "associado": self.id,
            "celular": contato.celular,
            "email": contato.email,
            "orgao_publico": contato.orgao_publico,
            "situacao_servidor": contato.situacao_servidor,
            "matricula_servidor": contato.matricula_servidor,
            "nome_contato": contato.nome_contato,
            "parentesco": contato.parentesco,
            "telefone_contato": contato.telefone_contato,
            "ultima_interacao_em": contato.ultima_interacao_em,
            "observacao": contato.observacao,
            "created_at": contato.created_at,
            "updated_at": contato.updated_at,
        }

    def sync_endereco_snapshot(self, endereco, save: bool = True):
        self.cep = endereco.cep or ""
        self.logradouro = endereco.logradouro or ""
        self.numero = endereco.numero or ""
        self.complemento = endereco.complemento or ""
        self.bairro = endereco.bairro or ""
        self.cidade = endereco.cidade or ""
        self.uf = endereco.uf or ""
        if save:
            self.save(
                update_fields=[
                    "cep",
                    "logradouro",
                    "numero",
                    "complemento",
                    "bairro",
                    "cidade",
                    "uf",
                    "updated_at",
                ]
            )

    def sync_dados_bancarios_snapshot(self, dados_bancarios, save: bool = True):
        self.banco = dados_bancarios.banco or ""
        self.agencia = dados_bancarios.agencia or ""
        self.conta = dados_bancarios.conta or ""
        self.tipo_conta = dados_bancarios.tipo_conta or ""
        self.chave_pix = dados_bancarios.chave_pix or ""
        if save:
            self.save(
                update_fields=[
                    "banco",
                    "agencia",
                    "conta",
                    "tipo_conta",
                    "chave_pix",
                    "updated_at",
                ]
            )

    def sync_contato_snapshot(self, contato, save: bool = True):
        self.telefone = contato.celular or ""
        self.email = contato.email or ""
        self.orgao_publico = contato.orgao_publico or ""
        self.situacao_servidor = contato.situacao_servidor or ""
        self.matricula_orgao = contato.matricula_servidor or ""
        if save:
            self.save(
                update_fields=[
                    "telefone",
                    "email",
                    "orgao_publico",
                    "situacao_servidor",
                    "matricula_orgao",
                    "updated_at",
                ]
            )

    def sync_contrato_snapshot(self, contrato, save: bool = True):
        self.contrato_mensalidade = contrato.valor_mensalidade
        self.contrato_prazo_meses = contrato.prazo_meses
        self.contrato_taxa_antecipacao = contrato.taxa_antecipacao
        self.contrato_margem_disponivel = contrato.margem_disponivel
        self.contrato_data_aprovacao = contrato.data_aprovacao
        self.contrato_data_envio_primeira = contrato.data_primeira_mensalidade
        self.contrato_valor_antecipacao = contrato.valor_total_antecipacao
        self.contrato_status_contrato = contrato.status
        self.contrato_mes_averbacao = contrato.mes_averbacao
        self.contrato_codigo_contrato = contrato.codigo
        self.contrato_doacao_associado = contrato.doacao_associado
        self.calc_valor_bruto = contrato.valor_bruto
        self.calc_liquido_cc = contrato.valor_liquido
        self.calc_prazo_antecipacao = contrato.prazo_meses
        self.calc_mensalidade_associativa = contrato.valor_mensalidade
        if save:
            self.save(
                update_fields=[
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
                    "updated_at",
                ]
            )

    def sync_documents_snapshot(self, save: bool = True):
        documents = []
        for documento in self.documentos.all():
            arquivo = documento.arquivo
            documents.append(
                {
                    "tipo": documento.tipo,
                    "status": documento.status,
                    "observacao": documento.observacao,
                    "relative_path": getattr(arquivo, "name", ""),
                    "arquivo": getattr(arquivo, "name", ""),
                    "uploaded_at": documento.created_at.isoformat()
                    if documento.created_at
                    else None,
                }
            )
        self.documents_json = documents
        if save:
            self.save(update_fields=["documents_json", "updated_at"])

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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.associado.sync_endereco_snapshot(self)


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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.associado.sync_dados_bancarios_snapshot(self)


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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.associado.sync_contato_snapshot(self)


class Documento(BaseModel):
    class Origem(models.TextChoices):
        OPERACIONAL = "operacional", "Operacional"
        LEGADO_CADASTRO = "legado_cadastro", "Legado cadastro"
        OUTRO = "outro", "Outro"

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
    arquivo_referencia_path = models.CharField(max_length=500, blank=True)
    nome_original = models.CharField(max_length=255, blank=True)
    origem = models.CharField(
        max_length=40,
        choices=Origem.choices,
        default=Origem.OPERACIONAL,
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDENTE
    )
    observacao = models.TextField(blank=True)

    class Meta:
        ordering = ["tipo"]

    def __str__(self) -> str:
        return f"{self.associado.nome_completo} - {self.tipo}"

    def save(self, *args, **kwargs):
        if self.arquivo and not self.arquivo_referencia_path:
            self.arquivo_referencia_path = getattr(self.arquivo, "name", "") or ""
        if self.arquivo and not self.nome_original:
            self.nome_original = getattr(self.arquivo, "name", "") or ""
        super().save(*args, **kwargs)
        self.associado.sync_documents_snapshot()

    @property
    def arquivo_referencia(self) -> str:
        if self.arquivo_referencia_path:
            return self.arquivo_referencia_path
        if not self.arquivo:
            return ""
        return str(getattr(self.arquivo, "name", "") or "")

    @property
    def arquivo_disponivel_localmente(self) -> bool:
        arquivo_name = str(getattr(self.arquivo, "name", "") or "")
        if not arquivo_name:
            return False
        try:
            return bool(default_storage.exists(arquivo_name))
        except Exception:
            return False


class AdminOverrideEvent(BaseModel):
    class Scope(models.TextChoices):
        ASSOCIADO = "associado", "Associado"
        CONTRATO = "contrato", "Contrato"
        CICLOS = "ciclos", "Ciclos"
        REFINANCIAMENTO = "refinanciamento", "Refinanciamento"
        ESTEIRA = "esteira", "Esteira"
        DOCUMENTO = "documento", "Documento"
        COMPROVANTE = "comprovante", "Comprovante"

    associado = models.ForeignKey(
        Associado,
        on_delete=models.CASCADE,
        related_name="admin_override_events",
    )
    contrato = models.ForeignKey(
        "contratos.Contrato",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_override_events",
    )
    ciclo = models.ForeignKey(
        "contratos.Ciclo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_override_events",
    )
    parcela = models.ForeignKey(
        "contratos.Parcela",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_override_events",
    )
    refinanciamento = models.ForeignKey(
        "refinanciamento.Refinanciamento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_override_events",
    )
    documento = models.ForeignKey(
        "associados.Documento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_override_events",
    )
    comprovante = models.ForeignKey(
        "refinanciamento.Comprovante",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_override_events",
    )
    realizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="admin_override_events",
    )
    revertida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admin_override_reversions",
    )
    escopo = models.CharField(max_length=32, choices=Scope.choices)
    resumo = models.CharField(max_length=255)
    motivo = models.TextField()
    before_snapshot = models.JSONField(default=dict, blank=True)
    after_snapshot = models.JSONField(default=dict, blank=True)
    confirmacao_dupla = models.BooleanField(default=True)
    revertida_em = models.DateTimeField(null=True, blank=True)
    motivo_reversao = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class AdminOverrideChange(BaseModel):
    class EntityType(models.TextChoices):
        ASSOCIADO = "associado", "Associado"
        CONTRATO = "contrato", "Contrato"
        CICLO = "ciclo", "Ciclo"
        PARCELA = "parcela", "Parcela"
        REFINANCIAMENTO = "refinanciamento", "Refinanciamento"
        DOCUMENTO = "documento", "Documento"
        COMPROVANTE = "comprovante", "Comprovante"
        ESTEIRA = "esteira", "Esteira"

    evento = models.ForeignKey(
        AdminOverrideEvent,
        on_delete=models.CASCADE,
        related_name="changes",
    )
    entity_type = models.CharField(max_length=32, choices=EntityType.choices)
    entity_id = models.PositiveIntegerField()
    competencia_referencia = models.DateField(null=True, blank=True)
    resumo = models.CharField(max_length=255)
    before_snapshot = models.JSONField(default=dict, blank=True)
    after_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["id"]


class Auxilio2Filiacao(BaseModel):
    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        PAGO = "pago", "Pago"
        EXPIRADO = "expirado", "Expirado"
        CANCELADO = "cancelado", "Cancelado"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="auxilio2_filiacoes",
    )
    associado = models.ForeignKey(
        Associado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auxilio2_filiacoes",
    )
    txid = models.CharField(max_length=255, unique=True, null=True, blank=True)
    charge_id = models.CharField(max_length=255, blank=True, db_index=True)
    loc_id = models.BigIntegerField(null=True, blank=True)
    valor = models.DecimalField(max_digits=10, decimal_places=2, default=30)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
    )
    pix_copia_cola = models.TextField(blank=True)
    imagem_qrcode = models.TextField(blank=True)
    raw = models.JSONField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["charge_id"]),
        ]

    def __str__(self) -> str:
        return f"Auxilio2 #{self.pk} - {self.user_id} - {self.status}"
