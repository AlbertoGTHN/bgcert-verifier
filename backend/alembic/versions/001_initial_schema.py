"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("admin", "compliance", "hr", "viewer", name="userrole"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("mfa_secret", sa.String(32), nullable=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Certificates table
    op.create_table(
        "certificates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("language_detected", sa.String(20), nullable=True),
        sa.Column("cert_type", sa.Enum(
            "criminal_background", "police_clearance", "government_clearance",
            "court_record", "unknown", name="certificatetype"
        ), nullable=True),
        sa.Column("holder_name", sa.String(500), nullable=True),
        sa.Column("holder_id", sa.String(100), nullable=True),
        sa.Column("cert_number", sa.String(200), nullable=True),
        sa.Column("issue_date", sa.String(50), nullable=True),
        sa.Column("expiry_date", sa.String(50), nullable=True),
        sa.Column("issuing_authority", sa.String(500), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("qr_code_found", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("qr_code_data", sa.Text(), nullable=True),
        sa.Column("qr_url", sa.Text(), nullable=True),
        sa.Column("qr_page_number", sa.Integer(), nullable=True),
        sa.Column("status", sa.Enum(
            "pending", "processing", "verified_authentic",
            "failed_fraudulent", "technical_issue", "error",
            name="validationstatus"
        ), nullable=False, server_default="pending"),
        sa.Column("validation_result", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("verification_url", sa.Text(), nullable=True),
        sa.Column("verification_domain", sa.String(500), nullable=True),
        sa.Column("is_official_domain", sa.Boolean(), nullable=True),
        sa.Column("verification_text", sa.Text(), nullable=True),
        sa.Column("screenshot_path", sa.String(1000), nullable=True),
        sa.Column("screenshot_url", sa.String(1000), nullable=True),
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("fraud_indicators", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("fraud_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("is_potentially_fraudulent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("processing_time_seconds", sa.Float(), nullable=True),
        sa.Column("job_id", sa.String(100), nullable=True),
        sa.Column("analyst_notes", sa.Text(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("uploaded_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_certificates_status", "certificates", ["status"])
    op.create_index("ix_certificates_job_id", "certificates", ["job_id"])

    # Audit logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("details", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="success"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("certificates")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS validationstatus")
    op.execute("DROP TYPE IF EXISTS certificatetype")
    op.execute("DROP TYPE IF EXISTS userrole")
