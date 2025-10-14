from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth.permissions import Permission, require_permissions
from ..schemas import UserRead

router = APIRouter()


@router.get("/")
async def relatorios(
    current_user: UserRead = Depends(require_permissions([Permission.RELATORIO_VIEW]))
):
    return {"relatorios": [], "user": current_user.email}
