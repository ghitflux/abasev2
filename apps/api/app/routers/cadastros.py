from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth.permissions import Permission, require_permissions
from ..schemas import UserRead

router = APIRouter()


@router.get("/")
async def list_cadastros(
    current_user: UserRead = Depends(require_permissions([Permission.CADASTRO_READ])),
):
    return {"items": [], "user": current_user.email}
