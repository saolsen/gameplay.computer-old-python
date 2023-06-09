"""timezones

Revision ID: 516ddfaaa55f
Revises: f4ed0977b4e9
Create Date: 2023-04-30 09:22:31.426505

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "516ddfaaa55f"
down_revision = "f4ed0977b4e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute(
        "ALTER TABLE matches ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE"
    )
    op.execute(
        "ALTER TABLE matches ALTER COLUMN finished_at TYPE TIMESTAMP WITH TIME ZONE"
    )
    op.execute(
        "ALTER TABLE match_turns ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE"
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
