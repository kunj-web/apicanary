"""Initial migration - create all tables

Revision ID: 278b5cf09bfc
Revises: 
Create Date: 2026-05-15 13:36:59.111572

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '278b5cf09bfc'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create users table
    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Create monitors table
    op.create_table('monitors',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('url', sa.String(length=2048), nullable=False),
    sa.Column('method', sa.String(length=10), nullable=False, server_default='GET'),
    sa.Column('headers', sa.JSON(), nullable=True),
    sa.Column('body', sa.JSON(), nullable=True),
    sa.Column('expected_status', sa.Integer(), nullable=False, server_default='200'),
    sa.Column('check_interval', sa.Integer(), nullable=False, server_default='5'),
    sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_monitors_user_id'), 'monitors', ['user_id'])

    # Create checks table
    op.create_table('checks',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('monitor_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.Integer(), nullable=False),
    sa.Column('response_time', sa.Integer(), nullable=True),
    sa.Column('status_code', sa.Integer(), nullable=True),
    sa.Column('response_body', sa.Text(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('checked_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['monitor_id'], ['monitors.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_checks_monitor_id'), 'checks', ['monitor_id'])
    op.create_index(op.f('ix_checks_checked_at'), 'checks', ['checked_at'])

    # Create alerts table
    op.create_table('alerts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('monitor_id', sa.UUID(), nullable=False),
    sa.Column('alert_type', sa.String(length=50), nullable=False),
    sa.Column('recipient', sa.String(length=500), nullable=False),
    sa.Column('threshold_failures', sa.Integer(), nullable=False, server_default='1'),
    sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['monitor_id'], ['monitors.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alerts_monitor_id'), 'alerts', ['monitor_id'])

    # Create incidents table
    op.create_table('incidents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('monitor_id', sa.UUID(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('duration_minutes', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=False, server_default='ongoing'),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['monitor_id'], ['monitors.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_incidents_monitor_id'), 'incidents', ['monitor_id'])

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_incidents_monitor_id'), table_name='incidents')
    op.drop_table('incidents')
    op.drop_index(op.f('ix_alerts_monitor_id'), table_name='alerts')
    op.drop_table('alerts')
    op.drop_index(op.f('ix_checks_checked_at'), table_name='checks')
    op.drop_index(op.f('ix_checks_monitor_id'), table_name='checks')
    op.drop_table('checks')
    op.drop_index(op.f('ix_monitors_user_id'), table_name='monitors')
    op.drop_table('monitors')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')