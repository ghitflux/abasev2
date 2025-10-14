from django.contrib import admin
from django.urls import path
from django.http import JsonResponse

from api.router import api

def api_info(request):
    return JsonResponse({
        "message": "ABASE v2 API",
        "version": "1.0.0",
        "endpoints": {
            "admin": "/admin/",
            "api": "/api/",
            "health": "/api/health",
            "auth": "/api/auth/",
            "cadastros": "/api/cadastros/",
            "analise": "/api/analise/",
            "tesouraria": "/api/tesouraria/",
            "sse": "/api/sse/"
        }
    })

urlpatterns = [
    path("", api_info, name="api_info"),
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
