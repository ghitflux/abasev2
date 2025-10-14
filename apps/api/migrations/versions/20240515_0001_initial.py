"""Initial FastAPI schema"""

from __future__ import annotations

from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20240515_0001"
down_revision = None
branch_labels = None
depends_on = None

cadastro_status_enum = sa.Enum(
    "RASCUNHO",
    "ENVIADO_ANALISE",
    "PENDENTE_CORRECAO",
    "APROVADO_ANALISE",
    "CANCELADO",
    "EM_TESOURARIA",
    "AGUARDANDO_COMPROVANTES",
    "EM_VALIDACAO_NUVIDEO",
    "CONTRATO_GERADO",
    "ASSINADO",
    "CONCLUIDO",
    name="cadastrostatus",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "roles",
            postgresql.ARRAY(sa.String(length=32)),
            nullable=False,
            server_default=sa.text("ARRAY[]::varchar[]"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "associados",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("cpf", sa.String(length=14), nullable=False),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("telefone", sa.String(length=20), nullable=True),
        sa.Column("endereco", sa.Text(), nullable=True),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_associados_cpf", "associados", ["cpf"], unique=True)

    cadastro_status_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "cadastros",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "associado_id",
            sa.Integer(),
            sa.ForeignKey("associados.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            cadastro_status_enum,
            nullable=False,
            server_default="RASCUNHO",
        ),
        sa.Column(
            "criado_por_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "atualizado_por_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_table(
        "event_logs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "idx_event_logs_entity",
        "event_logs",
        ["entity_type", "entity_id", "event_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_event_logs_entity", table_name="event_logs")
    op.drop_table("event_logs")

    op.drop_table("cadastros")
    cadastro_status_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_associados_cpf", table_name="associados")
    op.drop_table("associados")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
