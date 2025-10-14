from ninja import NinjaAPI
from .auth_router import router as auth_router
from .cadastros_router import router as cadastros_router
from .analise_router import router as analise_router
from .tesouraria_router import router as tesouraria_router
from .sse_router import router as sse_router

api = NinjaAPI(title="ABASE v2 API", version="1.0.0")

api.add_router("/auth", auth_router)
api.add_router("/cadastros", cadastros_router)
api.add_router("/analise", analise_router)
api.add_router("/tesouraria", tesouraria_router)
api.add_router("/sse", sse_router)


@api.get("/health")
def health_check(request):
    return {"status": "ok"}
