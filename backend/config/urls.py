from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter


def health_check(request):
    return JsonResponse({"status": "ok", "service": "abase-backend"})

from apps.associados.views import AssociadoViewSet
from apps.accounts.views import AdminUserViewSet
from apps.accounts.mobile_legacy_views import (
    LegacyCheckEmailView,
    LegacyForgotPasswordView,
    LegacyHomeView,
    LegacyLoginView,
    LegacyLogoutView,
    LegacyMeView,
    LegacyRegisterView,
    LegacyResetPasswordView,
)
from apps.contratos.views import ContratoViewSet
from apps.contratos.views import RenovacaoCicloViewSet
from apps.esteira.analise_views import AnaliseViewSet
from apps.esteira.views import EsteiraViewSet
from apps.importacao.views import ArquivoRetornoViewSet
from apps.refinanciamento.views import (
    AnalistaRefinanciamentoViewSet,
    CoordenadorRefinanciadosViewSet,
    CoordenadorRefinanciamentoViewSet,
    RefinanciamentoViewSet,
    TesourariaRefinanciamentoViewSet,
)
from apps.associados.mobile_views import (
    AppAntecipacaoView,
    AppDocumentosView,
    AppMensalidadesView,
    AppMeView,
    AppPendenciasView,
)
from apps.associados.mobile_legacy_views import (
    LegacyAntecipacaoHistoricoView,
    LegacyAssociadoA2StatusView,
    LegacyAssociadoDoisAceiteTermosView,
    LegacyAssociadoDoisAuxilio2ChargeView,
    LegacyAssociadoDoisAuxilio2ResumoView,
    LegacyAssociadoDoisAuxilio2StatusView,
    LegacyAssociadoDoisCadastroView,
    LegacyAssociadoDoisCheckCpfView,
    LegacyAssociadoDoisContatoView,
    LegacyAssociadoDoisIssuesView,
    LegacyAssociadoDoisReuploadsView,
    LegacyAssociadoDoisStatusView,
    LegacyAssociadoDoisAtualizarBasicoView,
    LegacyAssociadoMeView,
    LegacyAssociadoTermoAdesaoView,
    LegacyClientLogView,
    LegacyMensalidadesView,
)
from apps.relatorios.dashboard_views import AdminDashboardViewSet
from apps.relatorios.views import RelatorioViewSet
from apps.tesouraria.views import (
    AgentePagamentoViewSet,
    BaixaManualViewSet,
    DespesaViewSet,
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
    r"analise/refinanciamentos",
    AnalistaRefinanciamentoViewSet,
    basename="analise-refinanciamento",
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
router.register(
    r"tesouraria/baixa-manual",
    BaixaManualViewSet,
    basename="tesouraria-baixa-manual",
)
router.register(
    r"tesouraria/despesas",
    DespesaViewSet,
    basename="tesouraria-despesa",
)
router.register(r"relatorios", RelatorioViewSet, basename="relatorio")
router.register(r"dashboard/admin", AdminDashboardViewSet, basename="admin-dashboard")
router.register(
    r"configuracoes/usuarios",
    AdminUserViewSet,
    basename="configuracoes-usuarios",
)

urlpatterns = [
    path("api/v1/health/", health_check, name="health-check"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include(router.urls)),
    # Mobile self-service endpoints
    path("api/v1/app/me/", AppMeView.as_view(), name="app-me"),
    path("api/v1/app/mensalidades/", AppMensalidadesView.as_view(), name="app-mensalidades"),
    path("api/v1/app/antecipacao/", AppAntecipacaoView.as_view(), name="app-antecipacao"),
    path("api/v1/app/pendencias/", AppPendenciasView.as_view(), name="app-pendencias"),
    path("api/v1/app/documentos/", AppDocumentosView.as_view(), name="app-documentos"),
    # Mobile legacy facade
    path("api/login", LegacyLoginView.as_view(), name="legacy-mobile-login"),
    path("api/logout", LegacyLogoutView.as_view(), name="legacy-mobile-logout"),
    path("api/home", LegacyHomeView.as_view(), name="legacy-mobile-home"),
    path("api/me", LegacyMeView.as_view(), name="legacy-mobile-me"),
    path("api/auth/register", LegacyRegisterView.as_view(), name="legacy-mobile-register"),
    path("api/auth/check-email", LegacyCheckEmailView.as_view(), name="legacy-mobile-check-email"),
    path(
        "api/auth/forgot-password",
        LegacyForgotPasswordView.as_view(),
        name="legacy-mobile-forgot-password",
    ),
    path(
        "api/auth/reset-password",
        LegacyResetPasswordView.as_view(),
        name="legacy-mobile-reset-password",
    ),
    path("api/app/mensalidades", LegacyMensalidadesView.as_view(), name="legacy-mobile-mensalidades"),
    path(
        "api/app/mensalidades/ciclo",
        LegacyMensalidadesView.as_view(),
        name="legacy-mobile-mensalidades-ciclo",
    ),
    path(
        "api/app/antecipacao/historico",
        LegacyAntecipacaoHistoricoView.as_view(),
        name="legacy-mobile-antecipacao-historico",
    ),
    path("api/app/client-log", LegacyClientLogView.as_view(), name="legacy-mobile-client-log"),
    path(
        "api/associadodois/atualizar-basico",
        LegacyAssociadoDoisAtualizarBasicoView.as_view(),
        name="legacy-mobile-associadodois-atualizar-basico",
    ),
    path(
        "api/associadodois/check-cpf",
        LegacyAssociadoDoisCheckCpfView.as_view(),
        name="legacy-mobile-associadodois-check-cpf",
    ),
    path(
        "api/associadodois/status",
        LegacyAssociadoDoisStatusView.as_view(),
        name="legacy-mobile-associadodois-status",
    ),
    path(
        "api/associadodois/cadastro",
        LegacyAssociadoDoisCadastroView.as_view(),
        name="legacy-mobile-associadodois-cadastro",
    ),
    path(
        "api/associadodois/issues/my",
        LegacyAssociadoDoisIssuesView.as_view(),
        name="legacy-mobile-associadodois-issues",
    ),
    path(
        "api/associadodois/reuploads",
        LegacyAssociadoDoisReuploadsView.as_view(),
        name="legacy-mobile-associadodois-reuploads",
    ),
    path(
        "api/associadodois/aceite-termos",
        LegacyAssociadoDoisAceiteTermosView.as_view(),
        name="legacy-mobile-associadodois-aceite-termos",
    ),
    path(
        "api/associadodois/contato",
        LegacyAssociadoDoisContatoView.as_view(),
        name="legacy-mobile-associadodois-contato",
    ),
    path(
        "api/associadodois/auxilio2/status",
        LegacyAssociadoDoisAuxilio2StatusView.as_view(),
        name="legacy-mobile-associadodois-auxilio2-status",
    ),
    path(
        "api/associadodois/auxilio2/resumo",
        LegacyAssociadoDoisAuxilio2ResumoView.as_view(),
        name="legacy-mobile-associadodois-auxilio2-resumo",
    ),
    path(
        "api/associadodois/auxilio2/charge-30",
        LegacyAssociadoDoisAuxilio2ChargeView.as_view(),
        name="legacy-mobile-associadodois-auxilio2-charge",
    ),
    path("api/associado/me", LegacyAssociadoMeView.as_view(), name="legacy-mobile-associado-me"),
    path(
        "api/associado/a2/status",
        LegacyAssociadoA2StatusView.as_view(),
        name="legacy-mobile-associado-a2-status",
    ),
    path(
        "api/associado/termo-adesao",
        LegacyAssociadoTermoAdesaoView.as_view(),
        name="legacy-mobile-associado-termo-adesao",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
