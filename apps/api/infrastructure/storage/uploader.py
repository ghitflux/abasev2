"""
Sistema de Upload de Arquivos

Gerencia upload, validação e armazenamento de arquivos
"""
import os
import hashlib
import mimetypes
from pathlib import Path
from typing import Optional, Tuple
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from datetime import datetime


class UploadError(Exception):
    """Erro durante upload"""
    pass


class FileUploader:
    """Gerenciador de uploads de arquivos"""

    # Tamanhos máximos por tipo (em bytes)
    MAX_SIZES = {
        'documento': 10 * 1024 * 1024,  # 10MB
        'comprovante': 5 * 1024 * 1024,  # 5MB
        'foto': 3 * 1024 * 1024,  # 3MB
        'contrato': 15 * 1024 * 1024,  # 15MB
    }

    # Tipos MIME permitidos
    ALLOWED_MIMES = {
        'documento': [
            'application/pdf',
            'image/jpeg',
            'image/jpg',
            'image/png',
        ],
        'comprovante': [
            'application/pdf',
            'image/jpeg',
            'image/jpg',
            'image/png',
        ],
        'foto': [
            'image/jpeg',
            'image/jpg',
            'image/png',
        ],
        'contrato': [
            'application/pdf',
        ],
    }

    # Extensões permitidas
    ALLOWED_EXTENSIONS = {
        'documento': ['.pdf', '.jpg', '.jpeg', '.png'],
        'comprovante': ['.pdf', '.jpg', '.jpeg', '.png'],
        'foto': ['.jpg', '.jpeg', '.png'],
        'contrato': ['.pdf'],
    }

    def __init__(self, base_path: Optional[str] = None):
        """
        Inicializa uploader

        Args:
            base_path: Caminho base para armazenamento (padrão: MEDIA_ROOT)
        """
        if base_path:
            self.base_path = Path(base_path)
        else:
            self.base_path = Path(settings.BASE_DIR) / 'media'

        # Criar diretório se não existir
        self.base_path.mkdir(parents=True, exist_ok=True)

    def upload(
        self,
        file: UploadedFile,
        tipo: str,
        entity_type: str,
        entity_id: str,
        **metadata
    ) -> Tuple[str, str]:
        """
        Faz upload de um arquivo

        Args:
            file: Arquivo enviado
            tipo: Tipo do arquivo (documento, comprovante, foto, contrato)
            entity_type: Tipo da entidade (Cadastro, Associado, etc)
            entity_id: ID da entidade
            **metadata: Metadados adicionais

        Returns:
            Tuple (caminho_relativo, url_completa)

        Raises:
            UploadError: Se houver erro no upload
        """
        # Validar tipo
        if tipo not in self.MAX_SIZES:
            raise UploadError(f"Tipo de arquivo inválido: {tipo}")

        # Validar tamanho
        if file.size > self.MAX_SIZES[tipo]:
            max_mb = self.MAX_SIZES[tipo] / (1024 * 1024)
            raise UploadError(
                f"Arquivo muito grande. Máximo: {max_mb}MB. Tamanho: {file.size / (1024 * 1024):.2f}MB"
            )

        # Validar MIME type
        mime_type = file.content_type
        if mime_type not in self.ALLOWED_MIMES[tipo]:
            raise UploadError(
                f"Tipo de arquivo não permitido: {mime_type}. Permitidos: {', '.join(self.ALLOWED_MIMES[tipo])}"
            )

        # Validar extensão
        file_ext = Path(file.name).suffix.lower()
        if file_ext not in self.ALLOWED_EXTENSIONS[tipo]:
            raise UploadError(
                f"Extensão não permitida: {file_ext}. Permitidas: {', '.join(self.ALLOWED_EXTENSIONS[tipo])}"
            )

        # Sanitizar nome do arquivo
        safe_name = self._sanitize_filename(file.name)

        # Gerar caminho organizado
        # Estrutura: tipo/entity_type/entity_id/ano/mes/arquivo
        now = datetime.now()
        relative_path = Path(
            tipo,
            entity_type.lower(),
            str(entity_id),
            str(now.year),
            f"{now.month:02d}"
        )

        # Criar diretórios
        full_dir = self.base_path / relative_path
        full_dir.mkdir(parents=True, exist_ok=True)

        # Gerar nome único com hash
        file_hash = self._generate_hash(file)
        unique_name = f"{file_hash}_{safe_name}"
        full_path = full_dir / unique_name

        # Salvar arquivo
        try:
            with open(full_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
        except Exception as e:
            raise UploadError(f"Erro ao salvar arquivo: {str(e)}")

        # Construir URL relativa
        url_path = str(relative_path / unique_name).replace('\\', '/')

        # URL completa (simplificado - em produção usar MEDIA_URL)
        full_url = f"/media/{url_path}"

        return url_path, full_url

    def delete(self, file_path: str) -> bool:
        """
        Deleta um arquivo

        Args:
            file_path: Caminho relativo do arquivo

        Returns:
            True se deletado, False se não encontrado
        """
        full_path = self.base_path / file_path

        if not full_path.exists():
            return False

        try:
            full_path.unlink()
            return True
        except Exception:
            return False

    def get_url(self, file_path: str) -> str:
        """
        Retorna URL completa do arquivo

        Args:
            file_path: Caminho relativo

        Returns:
            URL completa
        """
        return f"/media/{file_path.replace(os.sep, '/')}"

    def exists(self, file_path: str) -> bool:
        """
        Verifica se arquivo existe

        Args:
            file_path: Caminho relativo

        Returns:
            True se existe
        """
        full_path = self.base_path / file_path
        return full_path.exists()

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitiza nome do arquivo

        Args:
            filename: Nome original

        Returns:
            Nome sanitizado
        """
        # Remover caracteres especiais
        name = Path(filename).stem
        ext = Path(filename).suffix

        # Manter apenas letras, números, hífens e underscores
        safe_name = ''.join(
            c for c in name if c.isalnum() or c in ('-', '_')
        )

        # Limitar tamanho
        safe_name = safe_name[:50]

        return f"{safe_name}{ext}"

    def _generate_hash(self, file: UploadedFile) -> str:
        """
        Gera hash do arquivo para nome único

        Args:
            file: Arquivo

        Returns:
            Hash MD5 (primeiros 8 caracteres)
        """
        md5 = hashlib.md5()

        # Ler arquivo em chunks
        for chunk in file.chunks():
            md5.update(chunk)

        # Resetar ponteiro do arquivo
        file.seek(0)

        return md5.hexdigest()[:8]


# Instância global
_uploader = None


def get_uploader() -> FileUploader:
    """Retorna instância global do uploader"""
    global _uploader
    if _uploader is None:
        _uploader = FileUploader()
    return _uploader
