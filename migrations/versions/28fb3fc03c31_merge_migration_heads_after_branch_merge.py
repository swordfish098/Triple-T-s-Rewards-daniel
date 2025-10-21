"""Merge migration heads after branch merge

Revision ID: 28fb3fc03c31
Revises: 9056a749bef5, 9dbfcc4fe50e
Create Date: 2025-10-21 10:27:45.814084

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '28fb3fc03c31'
down_revision = ('9056a749bef5', '9dbfcc4fe50e')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
