from .exception_handlers import register_handlers
from .v1.router import api as v1_api

register_handlers(v1_api)

api = v1_api
