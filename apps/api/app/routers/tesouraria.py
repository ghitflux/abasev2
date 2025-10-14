from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth.permissions import Permission, require_permissions
from ..schemas import UserRead

router = APIRouter()


@router.get("/fluxo")
async def fluxo_tesouraria(
    current_user: UserRead = Depends(require_permissions([Permission.TESOURARIA_VIEW]))
):
    return {"fluxo": [], "user": current_user.email}
