"""normalize

Revision ID: 7fb740bc8fa0
Revises: 5abff25e0f87
Create Date: 2023-04-24 07:58:57.107129

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "7fb740bc8fa0"
down_revision = "5abff25e0f87"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("matches", "updated_at")
    op.drop_column("matches", "next_player")
    op.drop_column("matches", "turn")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "matches",
        sa.Column("turn", sa.INTEGER(), autoincrement=False, nullable=False),
    )
    op.add_column(
        "matches",
        sa.Column("next_player", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "matches",
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(),
            autoincrement=False,
            nullable=False,
        ),
    )
    # ### end Alembic commands ###