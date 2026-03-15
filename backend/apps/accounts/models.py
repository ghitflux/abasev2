from __future__ import annotations

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from core.models import AllObjectsManager, BaseModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("O email é obrigatório.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email, password, **extra_fields)


class Role(BaseModel):
    codigo = models.CharField(max_length=30, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    must_set_password = models.BooleanField(default=True)
    profile_photo_path = models.CharField(max_length=2048, blank=True)
    roles = models.ManyToManyField(Role, through="UserRole", related_name="users")

    objects = UserManager()
    all_objects = AllObjectsManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ["first_name", "last_name", "email"]

    def __str__(self) -> str:
        return self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def primary_role(self) -> str | None:
        user_role = (
            self.user_roles.filter(deleted_at__isnull=True)
            .select_related("role")
            .order_by("role_id")
            .first()
        )
        return user_role.role.codigo if user_role else None

    def has_role(self, *codigos: str) -> bool:
        return self.user_roles.filter(
            deleted_at__isnull=True,
            role__codigo__in=codigos,
        ).exists()


class UserRole(BaseModel):
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="role_users")
    assigned_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("user", "role")
        ordering = ["user_id", "role_id"]

    def __str__(self) -> str:
        return f"{self.user.email} -> {self.role.codigo}"


class AgenteMargemConfig(BaseModel):
    """Percentual de margem/comissão vigente de um agente (agente_margens)."""

    agente = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="margem_configs"
    )
    percentual = models.DecimalField(max_digits=6, decimal_places=2, default=10)
    vigente_desde = models.DateTimeField(default=timezone.now)
    vigente_ate = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="margem_updates",
    )
    motivo = models.CharField(max_length=190, blank=True)

    class Meta:
        ordering = ["-vigente_desde"]

    def __str__(self) -> str:
        return f"{self.agente.email} - {self.percentual}%"


class AgenteMargemHistorico(BaseModel):
    """Histórico de alterações de margem de um agente (agente_margem_historicos)."""

    agente = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="margem_historicos"
    )
    percentual_anterior = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    percentual_novo = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="margem_changes",
    )
    motivo = models.CharField(max_length=190, blank=True)
    meta = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.agente.email}: {self.percentual_anterior} → {self.percentual_novo}"


class AgenteMargemSnapshot(BaseModel):
    """Snapshot de margem no momento de um cadastro (agente_margem_snapshots)."""

    cadastro = models.ForeignKey(
        "associados.Associado",
        on_delete=models.PROTECT,
        related_name="margem_snapshots",
    )
    agente = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="margem_snapshots"
    )
    percentual_anterior = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    percentual_novo = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    mensalidade = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    margem_disponivel = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    auxilio_valor_anterior = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    auxilio_valor_novo = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="margem_snapshot_changes",
    )
    motivo = models.CharField(max_length=190, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Snapshot {self.cadastro_id} - {self.agente.email}"
