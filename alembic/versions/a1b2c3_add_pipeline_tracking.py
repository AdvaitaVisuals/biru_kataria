"""Add pipeline tracking columns

Revision ID: a1b2c3
Revises: 3e7aa64a7df9
Create Date: 2026-02-12
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3'
down_revision = '3e7aa64a7df9'
branch_labels = None
depends_on = None


def upgrade():
    # Pipeline tracking on content_assets
    op.add_column('content_assets', sa.Column('pipeline_step', sa.Integer(), server_default='0'))
    op.add_column('content_assets', sa.Column('pipeline_step_status', sa.String(), server_default='PENDING'))
    op.add_column('content_assets', sa.Column('pipeline_data', sa.JSON(), nullable=True))

    # Auto-posting columns on posts
    op.add_column('posts', sa.Column('caption', sa.Text(), nullable=True))
    op.add_column('posts', sa.Column('post_url', sa.String(), nullable=True))
    op.add_column('posts', sa.Column('platform_post_id', sa.String(), nullable=True))


def downgrade():
    op.drop_column('content_assets', 'pipeline_step')
    op.drop_column('content_assets', 'pipeline_step_status')
    op.drop_column('content_assets', 'pipeline_data')
    op.drop_column('posts', 'caption')
    op.drop_column('posts', 'post_url')
    op.drop_column('posts', 'platform_post_id')
