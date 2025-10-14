from ninja.errors import ValidationError
from ninja import NinjaAPI


def register_handlers(api: NinjaAPI):
    @api.exception_handler(ValidationError)
    def on_validation_error(request, exc):
        return api.create_response(
            request, {"error": "validation_error", "details": exc.errors}, status=422
        )

    @api.exception_handler(Exception)
    def on_any_error(request, exc):
        return api.create_response(request, {"error": "internal_error"}, status=500)
