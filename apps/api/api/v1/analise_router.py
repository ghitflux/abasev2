from asgiref.sync import sync_to_async
from ninja import Router
from django.shortcuts import get_object_or_404
from core.models import Cadastro
from core.services.cadastro_service import CadastroService
from .schemas import CadastroOut

router = Router(tags=["analise"])


async def _get_cadastro_or_404(cad_id: int) -> Cadastro:
    return await sync_to_async(get_object_or_404, thread_sensitive=True)(Cadastro, id=cad_id)


@router.post("/cadastros/{cad_id}/aprovar", response=CadastroOut)
async def aprovar(request, cad_id: int):
    cadastro = await _get_cadastro_or_404(cad_id)
    cadastro = await sync_to_async(CadastroService.aprovar, thread_sensitive=True)(cadastro)
    return {
        "id": cadastro.id,
        "associado_id": cadastro.associado_id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }


@router.post("/cadastros/{cad_id}/pendenciar", response=CadastroOut)
async def pendenciar(request, cad_id: int, motivo: str):
    cadastro = await _get_cadastro_or_404(cad_id)
    cadastro = await sync_to_async(CadastroService.pendenciar, thread_sensitive=True)(cadastro, motivo)
    return {
        "id": cadastro.id,
        "associado_id": cadastro.associado_id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }


@router.post("/cadastros/{cad_id}/cancelar", response=CadastroOut)
async def cancelar(request, cad_id: int, motivo: str):
    cadastro = await _get_cadastro_or_404(cad_id)
    cadastro = await sync_to_async(CadastroService.cancelar, thread_sensitive=True)(cadastro, motivo)
    return {
        "id": cadastro.id,
        "associado_id": cadastro.associado_id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }
