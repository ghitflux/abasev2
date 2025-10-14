"""
Gerador de PDFs

Gera contratos e outros documentos em PDF
NOTA: Implementação básica. Em produção, considerar usar reportlab ou weasyprint
"""
from typing import Dict, Any, Optional
from datetime import datetime
from io import BytesIO


class PDFGeneratorError(Exception):
    """Erro na geração de PDF"""
    pass


class PDFGenerator:
    """Gerador de documentos PDF"""

    def __init__(self):
        """Inicializa gerador"""
        pass

    def gerar_contrato(
        self,
        dados_associado: Dict[str, Any],
        dados_cadastro: Dict[str, Any],
        dados_pagamento: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Gera contrato de associação em PDF

        Args:
            dados_associado: Dados do associado
            dados_cadastro: Dados do cadastro
            dados_pagamento: Dados do pagamento (opcional)

        Returns:
            Conteúdo do PDF em bytes

        Raises:
            PDFGeneratorError: Se houver erro na geração
        """
        try:
            # NOTA: Esta é uma implementação simplificada
            # Em produção, usar reportlab, weasyprint ou similar

            # Preparar dados
            nome = dados_associado.get('nome', 'N/A')
            cpf = dados_associado.get('cpf', 'N/A')
            email = dados_associado.get('email', 'N/A')
            cadastro_id = dados_cadastro.get('id', 'N/A')
            data_atual = datetime.now().strftime('%d/%m/%Y')

            # Gerar HTML (será convertido para PDF em produção)
            html_content = self._gerar_html_contrato(
                nome=nome,
                cpf=cpf,
                email=email,
                cadastro_id=cadastro_id,
                data=data_atual,
                dados_pagamento=dados_pagamento
            )

            # Mock: Por enquanto retornar um PDF mínimo válido
            # Em produção, usar biblioteca para converter HTML para PDF
            pdf_content = self._mock_pdf(html_content)

            return pdf_content

        except Exception as e:
            raise PDFGeneratorError(f"Erro ao gerar contrato: {str(e)}")

    def gerar_comprovante(
        self,
        dados_associado: Dict[str, Any],
        dados_pagamento: Dict[str, Any]
    ) -> bytes:
        """
        Gera comprovante de pagamento em PDF

        Args:
            dados_associado: Dados do associado
            dados_pagamento: Dados do pagamento

        Returns:
            Conteúdo do PDF em bytes
        """
        try:
            nome = dados_associado.get('nome', 'N/A')
            cpf = dados_associado.get('cpf', 'N/A')
            valor = dados_pagamento.get('valor', '0.00')
            forma_pagamento = dados_pagamento.get('forma_pagamento', 'N/A')
            data_pagamento = dados_pagamento.get('data_pagamento', 'N/A')

            html_content = self._gerar_html_comprovante(
                nome=nome,
                cpf=cpf,
                valor=valor,
                forma_pagamento=forma_pagamento,
                data=data_pagamento
            )

            pdf_content = self._mock_pdf(html_content)

            return pdf_content

        except Exception as e:
            raise PDFGeneratorError(f"Erro ao gerar comprovante: {str(e)}")

    def _gerar_html_contrato(
        self,
        nome: str,
        cpf: str,
        email: str,
        cadastro_id: str,
        data: str,
        dados_pagamento: Optional[Dict[str, Any]] = None
    ) -> str:
        """Gera HTML do contrato"""
        return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Contrato de Associação</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            line-height: 1.6;
        }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
        }}
        .title {{
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 20px;
        }}
        .section {{
            margin-bottom: 30px;
        }}
        .section-title {{
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
            border-bottom: 2px solid #333;
        }}
        .field {{
            margin: 10px 0;
        }}
        .label {{
            font-weight: bold;
        }}
        .signature {{
            margin-top: 60px;
            text-align: center;
        }}
        .signature-line {{
            border-top: 1px solid #000;
            width: 300px;
            margin: 0 auto;
            padding-top: 5px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="title">CONTRATO DE ASSOCIAÇÃO</div>
        <div>ABASE Manager - Sistema de Gestão de Associados</div>
        <div>Cadastro Nº: {cadastro_id}</div>
    </div>

    <div class="section">
        <div class="section-title">1. DADOS DO ASSOCIADO</div>
        <div class="field">
            <span class="label">Nome Completo:</span> {nome}
        </div>
        <div class="field">
            <span class="label">CPF:</span> {cpf}
        </div>
        <div class="field">
            <span class="label">E-mail:</span> {email}
        </div>
    </div>

    <div class="section">
        <div class="section-title">2. OBJETO DO CONTRATO</div>
        <p>
            O presente contrato tem por objeto a associação do CONTRATANTE à ABASE,
            com todos os direitos e deveres previstos no estatuto social.
        </p>
    </div>

    <div class="section">
        <div class="section-title">3. DIREITOS E DEVERES</div>
        <p>
            O ASSOCIADO terá direito a todos os benefícios previstos no estatuto
            e se compromete a cumprir com as obrigações estabelecidas.
        </p>
    </div>

    <div class="section">
        <div class="section-title">4. VIGÊNCIA</div>
        <p>
            Este contrato entra em vigor na data de sua assinatura e terá validade
            conforme previsto no estatuto social.
        </p>
    </div>

    <div class="section">
        <div class="field">
            <span class="label">Data:</span> {data}
        </div>
    </div>

    <div class="signature">
        <div class="signature-line">
            <div>{nome}</div>
            <div>CPF: {cpf}</div>
        </div>
    </div>

    <div style="margin-top: 60px; text-align: center; font-size: 10px; color: #666;">
        Documento gerado eletronicamente pelo ABASE Manager v2<br>
        ID do Documento: {cadastro_id} | Data de Geração: {data}
    </div>
</body>
</html>
        """

    def _gerar_html_comprovante(
        self,
        nome: str,
        cpf: str,
        valor: str,
        forma_pagamento: str,
        data: str
    ) -> str:
        """Gera HTML do comprovante"""
        return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Comprovante de Pagamento</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
            border-bottom: 3px solid #0072f5;
            padding-bottom: 20px;
        }}
        .title {{
            font-size: 24px;
            font-weight: bold;
            color: #0072f5;
        }}
        .field {{
            margin: 15px 0;
            padding: 10px;
            background: #f5f5f5;
        }}
        .label {{
            font-weight: bold;
            display: inline-block;
            width: 150px;
        }}
        .value {{
            color: #333;
        }}
        .total {{
            margin-top: 30px;
            padding: 15px;
            background: #0072f5;
            color: white;
            font-size: 20px;
            text-align: center;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="title">COMPROVANTE DE PAGAMENTO</div>
        <div>ABASE Manager</div>
    </div>

    <div class="field">
        <span class="label">Nome:</span>
        <span class="value">{nome}</span>
    </div>

    <div class="field">
        <span class="label">CPF:</span>
        <span class="value">{cpf}</span>
    </div>

    <div class="field">
        <span class="label">Data do Pagamento:</span>
        <span class="value">{data}</span>
    </div>

    <div class="field">
        <span class="label">Forma de Pagamento:</span>
        <span class="value">{forma_pagamento}</span>
    </div>

    <div class="total">
        VALOR: R$ {valor}
    </div>

    <div style="margin-top: 60px; text-align: center; font-size: 10px; color: #666;">
        Comprovante gerado eletronicamente pelo ABASE Manager v2<br>
        Data de Emissão: {data}
    </div>
</body>
</html>
        """

    def _mock_pdf(self, html_content: str) -> bytes:
        """
        Mock de geração de PDF

        NOTA: Em produção, usar biblioteca real (reportlab, weasyprint, etc)
        para converter HTML para PDF

        Args:
            html_content: Conteúdo HTML

        Returns:
            PDF básico em bytes
        """
        # Mock: Retornar um PDF mínimo válido com metadados
        pdf_header = b"%PDF-1.4\n"
        pdf_content = f"""
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 100
>>
stream
BT
/F1 12 Tf
50 700 Td
(ABASE Manager - Documento Gerado) Tj
0 -20 Td
(Este e um PDF de exemplo) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000315 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
465
%%EOF
        """.encode('latin-1')

        return pdf_header + pdf_content


# Instância global
_generator = None


def get_pdf_generator() -> PDFGenerator:
    """Retorna instância global do gerador de PDF"""
    global _generator
    if _generator is None:
        _generator = PDFGenerator()
    return _generator
