"""Initial schema: users, transcription jobs, segments and results.

Revision ID: 0001
Revises:
Create Date: 2026-10-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "transcription_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("client_id", sa.String(64), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(64), nullable=False),
        sa.Column("file_type", sa.String(10), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("requested_language", sa.String(10), nullable=False),
        sa.Column("detected_language", sa.String(10), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("transcription_progress", sa.Integer(), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("warning", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_transcription_jobs_user_id", "transcription_jobs", ["user_id"])
    op.create_index("ix_transcription_jobs_client_id", "transcription_jobs", ["client_id"])
    op.create_index("ix_transcription_jobs_status", "transcription_jobs", ["status"])
    op.create_index("ix_transcription_jobs_created_at", "transcription_jobs", ["created_at"])

    op.create_table(
        "transcription_segments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "job_id",
            sa.String(36),
            sa.ForeignKey("transcription_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
    )
    op.create_index("ix_transcription_segments_job_id", "transcription_segments", ["job_id"])

    op.create_table(
        "transcription_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "job_id",
            sa.String(36),
            sa.ForeignKey("transcription_jobs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(64), nullable=False),
        sa.Column("device", sa.String(16), nullable=True),
        sa.Column("processing_time", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("transcription_results")
    op.drop_index("ix_transcription_segments_job_id", table_name="transcription_segments")
    op.drop_table("transcription_segments")
    op.drop_index("ix_transcription_jobs_created_at", table_name="transcription_jobs")
    op.drop_index("ix_transcription_jobs_status", table_name="transcription_jobs")
    op.drop_index("ix_transcription_jobs_client_id", table_name="transcription_jobs")
    op.drop_index("ix_transcription_jobs_user_id", table_name="transcription_jobs")
    op.drop_table("transcription_jobs")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
