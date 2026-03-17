from django.db import models

from core.models import BaseModel


class RelatorioGerado(BaseModel):
    nome = models.CharField(max_length=255)
    formato = models.CharField(max_length=20)
    arquivo = models.FileField(upload_to="relatorios/")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.nome
