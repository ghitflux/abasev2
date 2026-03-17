from __future__ import annotations

from dataclasses import asdict, dataclass

from django.conf import settings
from django.core.files.storage import default_storage


@dataclass(frozen=True)
class FileReference:
    url: str
    arquivo_referencia: str
    arquivo_disponivel_localmente: bool
    tipo_referencia: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _build_absolute_url(request, path: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    if request:
        return request.build_absolute_uri(path)
    return path


def build_storage_reference(
    path: str | None,
    *,
    request=None,
    missing_type: str = "legado_sem_arquivo",
    local_type: str = "local",
) -> FileReference:
    if not path:
        return FileReference("", "", False, "")

    if path.startswith(("http://", "https://")):
        return FileReference(path, path, True, local_type)

    normalized_path = path.lstrip("/")
    try:
        exists = bool(default_storage.exists(normalized_path))
    except Exception:
        exists = False

    if not exists and path.startswith(settings.MEDIA_URL):
        normalized_path = path.removeprefix(settings.MEDIA_URL).lstrip("/")
        try:
            exists = bool(default_storage.exists(normalized_path))
        except Exception:
            exists = False

    if exists:
        try:
            url = default_storage.url(normalized_path)
        except Exception:
            url = f"{settings.MEDIA_URL.rstrip('/')}/{normalized_path}"
        return FileReference(
            _build_absolute_url(request, url),
            path,
            True,
            local_type,
        )

    return FileReference("", path, False, missing_type)


def build_filefield_reference(
    arquivo,
    *,
    request=None,
    missing_type: str = "legado_sem_arquivo",
    local_type: str = "local",
) -> FileReference:
    if not arquivo:
        return FileReference("", "", False, "")

    try:
        path = getattr(arquivo, "name", "") or ""
    except Exception:
        path = ""

    return build_storage_reference(
        path,
        request=request,
        missing_type=missing_type,
        local_type=local_type,
    )
