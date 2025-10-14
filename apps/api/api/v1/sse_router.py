"""
Server-Sent Events (SSE) Router

Endpoint para streaming de eventos em tempo real
"""
import json
from ninja import Router
from django.http import StreamingHttpResponse
from infrastructure.cache.redis_client import get_client

router = Router(tags=["sse"])


@router.get("/stream")
def stream(request):
    """
    Stream de eventos SSE

    Eventos publicados no canal Redis 'events:all' são transmitidos
    em tempo real para os clientes conectados.

    Eventos disponíveis:
    - CADASTRO_CRIADO
    - CADASTRO_SUBMETIDO
    - CADASTRO_APROVADO
    - CADASTRO_PENDENTE
    - CADASTRO_CANCELADO
    - PAGAMENTO_RECEBIDO
    - COMPROVANTES_ANEXADOS
    - ENVIADO_NUVIDEO
    - CONTRATO_GERADO
    - CONTRATO_ASSINADO
    - CADASTRO_CONCLUIDO
    """
    channel = "events:all"
    client = get_client()
    pubsub = client.pubsub()
    pubsub.subscribe(channel)

    def event_stream():
        # Enviar retry time
        yield "retry: 5000\n\n"

        # Enviar evento inicial de conexão
        yield f"data: {json.dumps({'type': 'CONNECTED', 'timestamp': 'now'})}\n\n"

        # Stream de eventos
        for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]

                # Decodificar se for bytes
                if isinstance(data, bytes):
                    data = data.decode("utf-8")

                # Tentar parsear como JSON
                try:
                    json_data = json.loads(data)
                    data = json.dumps(json_data)
                except (json.JSONDecodeError, TypeError):
                    # Se não for JSON, enviar como string
                    pass

                yield f"data: {data}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # Desabilitar buffering no nginx
    return response
