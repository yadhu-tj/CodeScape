"""Phase 1 PostgreSQL baseline"""

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        'repos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('source_url', sa.String(length=500), nullable=True),
        sa.Column('commit_sha', sa.String(length=64), nullable=True),
        sa.Column('local_path', sa.String(length=500), nullable=False),
        sa.Column('image_tag', sa.String(length=150), server_default='codescape-sandbox:latest', nullable=False),
        sa.Column('status', sa.String(length=30), server_default='ready', nullable=False),
        sa.Column('ingested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'nodes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('repo_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('qualified_name', sa.String(length=350), nullable=False),
        sa.Column('file_path', sa.String(length=350), nullable=False),
        sa.Column('start_line', sa.Integer(), nullable=False),
        sa.Column('end_line', sa.Integer(), nullable=False),
        sa.Column('signature', sa.Text(), nullable=True),
        sa.Column('docstring', sa.Text(), nullable=True),
        sa.Column('route_path', sa.String(length=250), nullable=True),
        sa.Column('complexity', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('body_text', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(768), nullable=True),
        sa.ForeignKeyConstraint(['repo_id'], ['repos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_nodes_embedding_hnsw', 'nodes', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index('idx_nodes_qualified_name', 'nodes', ['repo_id', 'qualified_name'], unique=False)
    op.create_index('idx_nodes_repo_id', 'nodes', ['repo_id'], unique=False)
    op.create_table(
        'chaos_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('repo_id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.Integer(), nullable=False),
        sa.Column('blamed_node_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='queued', nullable=False),
        sa.Column('classification', sa.String(length=40), nullable=True),
        sa.Column('test_code', sa.Text(), nullable=True),
        sa.Column('report', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True),
        sa.Column('log_ref', sa.Text(), nullable=True),
        sa.Column('seed_key', sa.String(length=150), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['blamed_node_id'], ['nodes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['repo_id'], ['repos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('seed_key'),
    )
    op.create_index('idx_chaos_runs_node_id', 'chaos_runs', ['node_id'], unique=False)
    op.create_table(
        'edges',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('repo_id', sa.Integer(), nullable=False),
        sa.Column('src_node_id', sa.Integer(), nullable=False),
        sa.Column('dst_node_id', sa.Integer(), nullable=True),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('confidence', sa.String(length=20), nullable=False),
        sa.Column('call_site_line', sa.Integer(), nullable=True),
        sa.Column('raw_callee_expr', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['dst_node_id'], ['nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['repo_id'], ['repos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['src_node_id'], ['nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_edges_dst_node_id', 'edges', ['dst_node_id'], unique=False)
    op.create_index('idx_edges_repo_id', 'edges', ['repo_id'], unique=False)
    op.create_index('idx_edges_src_node_id', 'edges', ['src_node_id'], unique=False)
    op.create_table(
        'patches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('node_id', sa.Integer(), nullable=False),
        sa.Column('replacement_code', sa.Text(), nullable=False),
        sa.Column('unified_diff', sa.Text(), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='proposed', nullable=False),
        sa.Column('verification_report', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('seed_key', sa.String(length=150), nullable=True),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['run_id'], ['chaos_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('seed_key'),
    )
    op.create_table(
        'run_events',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('seq', sa.BigInteger(), nullable=False),
        sa.Column('event', sa.String(length=80), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['chaos_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id', 'seq'),
    )
    op.create_index('idx_run_events_run_seq', 'run_events', ['run_id', 'seq'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_run_events_run_seq', table_name='run_events')
    op.drop_table('run_events')
    op.drop_table('patches')
    op.drop_index('idx_edges_src_node_id', table_name='edges')
    op.drop_index('idx_edges_repo_id', table_name='edges')
    op.drop_index('idx_edges_dst_node_id', table_name='edges')
    op.drop_table('edges')
    op.drop_index('idx_chaos_runs_node_id', table_name='chaos_runs')
    op.drop_table('chaos_runs')
    op.drop_index('idx_nodes_repo_id', table_name='nodes')
    op.drop_index('idx_nodes_qualified_name', table_name='nodes')
    op.drop_index('idx_nodes_embedding_hnsw', table_name='nodes', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_table('nodes')
    op.drop_table('repos')
