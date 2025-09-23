"""add lockout and reset fields to users

Revision ID: 5328a0ca9db5
Revises: 2f5bfe168650
Create Date: 2025-09-22 17:17:27.375402
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '5328a0ca9db5'
down_revision = '2f5bfe168650'
branch_labels = None
depends_on = None


def upgrade():
    # Add the four columns to USERS. We give failed_attempts a temporary server_default
    # so existing rows can be populated during migration, then we drop that default.
    with op.batch_alter_table('USERS', schema=None) as batch_op:
        batch_op.add_column(sa.Column('failed_attempts', sa.Integer(), nullable=False, server_default=text('0')))
        batch_op.add_column(sa.Column('lockout_time', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('reset_token', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('reset_token_created_at', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_USERS_reset_token', ['reset_token'], unique=False)

    # Remove the server default so future inserts rely on app logic
    op.alter_column('USERS', 'failed_attempts', server_default=None)


def downgrade():
    with op.batch_alter_table('USERS', schema=None) as batch_op:
        batch_op.drop_index('ix_USERS_reset_token')
        batch_op.drop_column('reset_token_created_at')
        batch_op.drop_column('reset_token')
        batch_op.drop_column('lockout_time')
        batch_op.drop_column('failed_attempts')
