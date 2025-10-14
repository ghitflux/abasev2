"""
Tesouraria Router

Endpoints para gerenciar o pipeline de tesouraria
"""
from decimal import Decimal
from datetime import datetime
from asgiref.sync import sync_to_async
from ninja import Router, Schema
from ninja.errors import HttpError
from django.shortcuts import get_object_or_404
from typing import Optional

from core.models import Cadastro, Associado
from core.services.tesouraria_service import TesourariaService
from infrastructure.storage.uploader import get_uploader
from infrastructure.pdf.generator import get_pdf_generator
from infrastructure.nuvideo.client import get_nuvideo_client
from .schemas import CadastroOut

router = Router(tags=["tesouraria"])


# Schemas específicos
class PagamentoIn(Schema):
    valor: float
    forma_pagamento: str
    data_pagamento: str  # ISO format
    referencia: Optional[str] = None


class ProgressoOut(Schema):
    cadastro_id: int
    status: str
    progresso_percentual: float
    etapas_concluidas: int
    total_etapas: int


async def _get_cadastro_or_404(cad_id: int) -> Cadastro:
    return await sync_to_async(get_object_or_404, thread_sensitive=True)(Cadastro, id=cad_id)


@router.post("/cadastros/{cad_id}/receber-pagamento", response=CadastroOut)
async def receber_pagamento(request, cad_id: int, payload: PagamentoIn):
    """Registra recebimento de pagamento"""
    cadastro = await _get_cadastro_or_404(cad_id)

    # Converter data
    data_pagamento = datetime.fromisoformat(payload.data_pagamento)

    # Registrar pagamento
    cadastro = await sync_to_async(
        TesourariaService.registrar_pagamento,
        thread_sensitive=True
    )(
        cadastro=cadastro,
        valor=Decimal(str(payload.valor)),
        forma_pagamento=payload.forma_pagamento,
        data_pagamento=data_pagamento,
        referencia=payload.referencia,
        actor_id=getattr(request, 'user_id', None)
    )

    return {
        "id": cadastro.id,
        "associado_id": cadastro.associado_id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }


@router.post("/cadastros/{cad_id}/upload-comprovante")
async def upload_comprovante(request, cad_id: int):
    """Upload de comprovante de pagamento"""
    cadastro = await _get_cadastro_or_404(cad_id)

    # Pegar arquivo do request
    if 'file' not in request.FILES:
        raise HttpError(400, "Nenhum arquivo enviado")

    file = request.FILES['file']

    # Upload do arquivo
    uploader = get_uploader()
    try:
        file_path, file_url = await sync_to_async(
            uploader.upload,
            thread_sensitive=True
        )(
            file=file,
            tipo='comprovante',
            entity_type='Cadastro',
            entity_id=str(cadastro.id)
        )

        return {
            "success": True,
            "file_path": file_path,
            "file_url": file_url,
        }
    except Exception as e:
        raise HttpError(400, f"Erro no upload: {str(e)}")


@router.post("/cadastros/{cad_id}/confirmar-comprovantes", response=CadastroOut)
async def confirmar_comprovantes(request, cad_id: int, comprovantes: list[str]):
    """Confirma que todos comprovantes foram anexados"""
    cadastro = await _get_cadastro_or_404(cad_id)

    cadastro = await sync_to_async(
        TesourariaService.confirmar_comprovantes,
        thread_sensitive=True
    )(
        cadastro=cadastro,
        comprovantes_urls=comprovantes,
        actor_id=getattr(request, 'user_id', None)
    )

    return {
        "id": cadastro.id,
        "associado_id": cadastro.associado_id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }


@router.post("/cadastros/{cad_id}/gerar-contrato")
async def gerar_contrato(request, cad_id: int):
    """Gera contrato em PDF"""
    cadastro = await _get_cadastro_or_404(cad_id)

    # Buscar associado
    associado = await sync_to_async(
        lambda: cadastro.associado,
        thread_sensitive=True
    )()

    # Preparar dados
    dados_associado = {
        "nome": associado.nome,
        "cpf": associado.cpf,
        "email": associado.email or "",
    }

    dados_cadastro = {
        "id": cadastro.id,
        "status": cadastro.status,
    }

    # Gerar PDF
    generator = get_pdf_generator()
    pdf_content = await sync_to_async(
        generator.gerar_contrato,
        thread_sensitive=True
    )(
        dados_associado=dados_associado,
        dados_cadastro=dados_cadastro
    )

    # Salvar PDF
    uploader = get_uploader()

    # Criar arquivo temporário
    from django.core.files.base import ContentFile
    pdf_file = ContentFile(pdf_content, name=f"contrato_{cadastro.id}.pdf")

    file_path, file_url = await sync_to_async(
        uploader.upload,
        thread_sensitive=True
    )(
        file=pdf_file,
        tipo='contrato',
        entity_type='Cadastro',
        entity_id=str(cadastro.id)
    )

    # Registrar no service
    cadastro = await sync_to_async(
        TesourariaService.gerar_contrato,
        thread_sensitive=True
    )(
        cadastro=cadastro,
        contrato_url=file_url,
        actor_id=getattr(request, 'user_id', None)
    )

    return {
        "success": True,
        "contrato_url": file_url,
        "cadastro_id": cadastro.id,
    }


@router.post("/cadastros/{cad_id}/enviar-nuvideo")
async def enviar_nuvideo(request, cad_id: int):
    """Envia contrato para assinatura no NuVideo"""
    cadastro = await _get_cadastro_or_404(cad_id)

    # Buscar associado
    associado = await sync_to_async(
        lambda: cadastro.associado,
        thread_sensitive=True
    )()

    # Mock: criar documento no NuVideo
    client = get_nuvideo_client()

    # Gerar PDF (simplificado)
    pdf_content = b"%PDF-1.4\nContrato Mock"

    # Criar documento
    doc_info = await client.criar_documento(
        nome=f"Contrato {cadastro.id}",
        descricao="Contrato de Associação",
        arquivo_pdf=pdf_content
    )

    documento_id = doc_info["documento_id"]

    # Enviar para assinatura
    signatarios = [
        {
            "nome": associado.nome,
            "email": associado.email or "associado@example.com",
            "cpf": associado.cpf,
        }
    ]

    envio_info = await client.enviar_para_assinatura(
        documento_id=documento_id,
        signatarios=signatarios
    )

    # Registrar no service
    cadastro = await sync_to_async(
        TesourariaService.enviar_para_nuvideo,
        thread_sensitive=True
    )(
        cadastro=cadastro,
        documento_id=documento_id,
        actor_id=getattr(request, 'user_id', None)
    )

    return {
        "success": True,
        "documento_id": documento_id,
        "signatarios": envio_info["signatarios"],
    }


@router.post("/cadastros/{cad_id}/confirmar-assinatura", response=CadastroOut)
async def confirmar_assinatura(request, cad_id: int, assinatura_id: str):
    """Confirma que contrato foi assinado"""
    cadastro = await _get_cadastro_or_404(cad_id)

    cadastro = await sync_to_async(
        TesourariaService.confirmar_assinatura,
        thread_sensitive=True
    )(
        cadastro=cadastro,
        assinatura_id=assinatura_id,
        assinatura_data=datetime.now(),
        actor_id=getattr(request, 'user_id', None)
    )

    return {
        "id": cadastro.id,
        "associado_id": cadastro.associado_id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }


@router.post("/cadastros/{cad_id}/concluir", response=CadastroOut)
async def concluir(request, cad_id: int, observacoes: Optional[str] = None):
    """Finaliza processo de cadastro"""
    cadastro = await _get_cadastro_or_404(cad_id)

    cadastro = await sync_to_async(
        TesourariaService.concluir_cadastro,
        thread_sensitive=True
    )(
        cadastro=cadastro,
        observacoes=observacoes,
        actor_id=getattr(request, 'user_id', None)
    )

    return {
        "id": cadastro.id,
        "associado_id": cadastro.associado_id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }


@router.get("/cadastros/{cad_id}/progresso", response=ProgressoOut)
async def obter_progresso(request, cad_id: int):
    """Obtém progresso do cadastro no pipeline"""
    cadastro = await _get_cadastro_or_404(cad_id)

    progresso = await sync_to_async(
        TesourariaService.obter_progresso,
        thread_sensitive=True
    )(cadastro)

    return progresso
