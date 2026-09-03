"""users.onboarded_at — 온보딩(이름 입력 + 약관·개인정보 동의) 완료 시각

Revision ID: 574baa8c8dcd
Revises: 3a987f72d183
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '574baa8c8dcd'
down_revision: Union[str, Sequence[str], None] = '3a987f72d183'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('onboarded_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('onboarded_at')
