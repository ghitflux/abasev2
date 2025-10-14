from asgiref.sync import sync_to_async
from ninja import Router
from ninja.errors import HttpError
from django.shortcuts import get_object_or_404
from core.models import Associado, Cadastro
from core.services.cadastro_service import CadastroService
from .schemas import AssociadoIn, AssociadoOut, CadastroIn, CadastroOut

router = Router(tags=["cadastros"])


async def _get_associado_or_404(assoc_id: int) -> Associado:
    return await sync_to_async(get_object_or_404, thread_sensitive=True)(Associado, id=assoc_id)


async def _get_cadastro_or_404(cad_id: int) -> Cadastro:
    return await sync_to_async(get_object_or_404, thread_sensitive=True)(Cadastro, id=cad_id)


@router.post("/associados", response=AssociadoOut)
async def criar_associado(request, payload: AssociadoIn):
    exists = await Associado.objects.filter(cpf=payload.cpf).aexists()
    if exists:
        raise HttpError(400, "cpf_duplicado")
    associado = await Associado.objects.acreate(**payload.dict())
    data = payload.dict()
    data["id"] = associado.id
    return data


@router.get("/associados/{assoc_id}", response=AssociadoOut)
async def obter_associado(request, assoc_id: int):
    associado = await _get_associado_or_404(assoc_id)
    return {
        "id": associado.id,
        "cpf": associado.cpf,
        "nome": associado.nome,
        "email": associado.email,
        "telefone": associado.telefone,
        "endereco": associado.endereco,
    }


@router.post("/cadastros", response=CadastroOut)
async def criar_cadastro(request, payload: CadastroIn):
    associado = await _get_associado_or_404(payload.associado_id)
    cadastro = await Cadastro.objects.acreate(associado=associado, observacao=payload.observacao)
    return {
        "id": cadastro.id,
        "associado_id": associado.id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }


@router.post("/cadastros/{cad_id}/submit", response=CadastroOut)
async def submit(request, cad_id: int):
    cadastro = await _get_cadastro_or_404(cad_id)
    cadastro = await sync_to_async(CadastroService.submit, thread_sensitive=True)(cadastro)
    return {
        "id": cadastro.id,
        "associado_id": cadastro.associado_id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }
