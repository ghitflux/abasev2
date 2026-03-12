from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import ValidationError

from .base import ImportacaoBaseTestCase
from ..parsers import normalize_lines
from ..validators import ArquivoRetornoValidator


class ArquivoRetornoValidatorTestCase(ImportacaoBaseTestCase):
    def test_validar_cabecalho_do_fixture(self):
        lines = normalize_lines(self.fixture_bytes().decode("utf-8"))

        ArquivoRetornoValidator.validar_cabecalho(lines)

    def test_validar_formato_rejeita_extensao_invalida(self):
        with self.assertRaises(ValidationError):
            ArquivoRetornoValidator.validar_formato("retorno.csv")

    def test_validar_item_rejeita_cpf_e_competencia_invalidos(self):
        with self.assertRaises(ValidationError) as ctx:
            ArquivoRetornoValidator.validar_item(
                {
                    "status_codigo": "9",
                    "cpf_cnpj": "123",
                    "competencia": "2025-05",
                    "valor_descontado": "-10.00",
                }
            )

        self.assertIn("status_codigo", ctx.exception.detail)
        self.assertIn("cpf_cnpj", ctx.exception.detail)
        self.assertIn("competencia", ctx.exception.detail)
        self.assertIn("valor_descontado", ctx.exception.detail)

    def test_validar_tamanho_rejeita_arquivo_acima_do_limite(self):
        arquivo = SimpleUploadedFile("retorno.txt", b"abc", content_type="text/plain")

        with self.assertRaises(ValidationError):
            ArquivoRetornoValidator.validar_tamanho(arquivo, max_mb=0)
