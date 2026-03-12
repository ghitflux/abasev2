from __future__ import annotations

from dataclasses import dataclass

from decouple import config

from apps.accounts.models import Role, User

DEFAULT_ROLES = (
    ("ADMIN", "Administrador", "Acesso total ao sistema."),
    ("AGENTE", "Agente", "Responsavel pelo cadastro inicial de associados."),
    ("ANALISTA", "Analista", "Validacao documental e analise inicial."),
    ("COORDENADOR", "Coordenador", "Segunda aprovacao do fluxo."),
    ("TESOUREIRO", "Tesoureiro", "Efetivacao financeira e confirmacoes."),
)


@dataclass(frozen=True)
class SeedUserSpec:
    role_code: str
    email: str
    first_name: str
    last_name: str
    password: str
    is_staff: bool = False
    is_superuser: bool = False


def default_seed_user_specs() -> list[SeedUserSpec]:
    default_password = config("DEV_DEFAULT_PASSWORD", default="Senha@123")
    return [
        SeedUserSpec(
            role_code="ADMIN",
            email=config("DEV_ADMIN_EMAIL", default="admin@abase.local"),
            first_name=config("DEV_ADMIN_FIRST_NAME", default="Admin"),
            last_name=config("DEV_ADMIN_LAST_NAME", default="ABASE"),
            password=config("DEV_ADMIN_PASSWORD", default="Admin@123"),
            is_staff=True,
            is_superuser=True,
        ),
        SeedUserSpec(
            role_code="AGENTE",
            email=config("DEV_AGENTE_EMAIL", default="agente@abase.local"),
            first_name=config("DEV_AGENTE_FIRST_NAME", default="Agente"),
            last_name=config("DEV_AGENTE_LAST_NAME", default="ABASE"),
            password=config("DEV_AGENTE_PASSWORD", default=default_password),
        ),
        SeedUserSpec(
            role_code="ANALISTA",
            email=config("DEV_ANALISTA_EMAIL", default="analista@abase.local"),
            first_name=config("DEV_ANALISTA_FIRST_NAME", default="Analista"),
            last_name=config("DEV_ANALISTA_LAST_NAME", default="ABASE"),
            password=config("DEV_ANALISTA_PASSWORD", default=default_password),
        ),
        SeedUserSpec(
            role_code="COORDENADOR",
            email=config("DEV_COORDENADOR_EMAIL", default="coordenador@abase.local"),
            first_name=config("DEV_COORDENADOR_FIRST_NAME", default="Coordenador"),
            last_name=config("DEV_COORDENADOR_LAST_NAME", default="ABASE"),
            password=config("DEV_COORDENADOR_PASSWORD", default=default_password),
        ),
        SeedUserSpec(
            role_code="TESOUREIRO",
            email=config("DEV_TESOUREIRO_EMAIL", default="tesoureiro@abase.local"),
            first_name=config("DEV_TESOUREIRO_FIRST_NAME", default="Tesoureiro"),
            last_name=config("DEV_TESOUREIRO_LAST_NAME", default="ABASE"),
            password=config("DEV_TESOUREIRO_PASSWORD", default=default_password),
        ),
    ]


def ensure_roles() -> dict[str, Role]:
    for codigo, nome, descricao in DEFAULT_ROLES:
        role = Role.all_objects.filter(codigo__iexact=codigo).first()
        if role is None:
            role = Role.all_objects.create(
                codigo=codigo,
                nome=nome,
                descricao=descricao,
                deleted_at=None,
            )
        else:
            role.codigo = codigo
            role.nome = nome
            role.descricao = descricao
            role.deleted_at = None
            role.save(update_fields=["codigo", "nome", "descricao", "deleted_at", "updated_at"])

    return {
        role.codigo.upper(): role
        for role in Role.objects.filter(codigo__in=[item[0] for item in DEFAULT_ROLES])
    }


def ensure_access_users() -> dict[str, SeedUserSpec]:
    roles = ensure_roles()
    specs = default_seed_user_specs()

    for spec in specs:
        user, _ = User.all_objects.get_or_create(
            email=spec.email,
            defaults={
                "first_name": spec.first_name,
                "last_name": spec.last_name,
                "is_active": True,
                "is_staff": spec.is_staff,
                "is_superuser": spec.is_superuser,
                "deleted_at": None,
            },
        )

        user.first_name = spec.first_name
        user.last_name = spec.last_name
        user.is_active = True
        user.is_staff = spec.is_staff
        user.is_superuser = spec.is_superuser
        user.deleted_at = None
        user.set_password(spec.password)
        user.save()
        user.roles.set([roles[spec.role_code]])

    return {spec.role_code: spec for spec in specs}
