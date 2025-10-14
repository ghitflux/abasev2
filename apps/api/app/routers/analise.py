from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth.permissions import Permission, require_permissions
from ..schemas import UserRead

router = APIRouter()


@router.get("/status")
async def analysis_status(
    current_user: UserRead = Depends(require_permissions([Permission.ANALISE_VIEW]))
):
    return {"status": "ok", "user": current_user.email}
