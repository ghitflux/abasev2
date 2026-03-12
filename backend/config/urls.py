from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.associados.views import AssociadoViewSet
from apps.contratos.views import ContratoViewSet
from apps.contratos.views import RenovacaoCicloViewSet
from apps.esteira.analise_views import AnaliseViewSet
from apps.esteira.views import EsteiraViewSet
from apps.importacao.views import ArquivoRetornoViewSet
from apps.refinanciamento.views import (
    CoordenadorRefinanciadosViewSet,
    CoordenadorRefinanciamentoViewSet,
    RefinanciamentoViewSet,
    TesourariaRefinanciamentoViewSet,
)
from apps.relatorios.views import RelatorioViewSet
from apps.tesouraria.views import (
    AgentePagamentoViewSet,
    ConfirmacaoViewSet,
    TesourariaContratoViewSet,
)

router = DefaultRouter()
router.register(r"associados", AssociadoViewSet, basename="associado")
router.register(r"analise", AnaliseViewSet, basename="analise")
router.register(r"esteira", EsteiraViewSet, basename="esteira")
router.register(r"contratos", ContratoViewSet, basename="contrato")
router.register(r"renovacao-ciclos", RenovacaoCicloViewSet, basename="renovacao-ciclo")
router.register(
    r"importacao/arquivo-retorno",
    ArquivoRetornoViewSet,
    basename="arquivo-retorno",
)
router.register(r"refinanciamentos", RefinanciamentoViewSet, basename="refinanciamento")
router.register(
    r"coordenacao/refinanciados",
    CoordenadorRefinanciadosViewSet,
    basename="coordenacao-refinanciados",
)
router.register(
    r"coordenacao/refinanciamento",
    CoordenadorRefinanciamentoViewSet,
    basename="coordenacao-refinanciamento",
)
router.register(
    r"tesouraria/contratos",
    TesourariaContratoViewSet,
    basename="tesouraria-contrato",
)
router.register(
    r"tesouraria/confirmacoes",
    ConfirmacaoViewSet,
    basename="tesouraria-confirmacao",
)
router.register(
    r"tesouraria/refinanciamentos",
    TesourariaRefinanciamentoViewSet,
    basename="tesouraria-refinanciamento",
)
router.register(r"agente/pagamentos", AgentePagamentoViewSet, basename="agente-pagamento")
router.register(r"relatorios", RelatorioViewSet, basename="relatorio")

urlpatterns = [
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include(router.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
