"""add character holdings and in-transit tables

Revision ID: 20260412_0017
Revises: 20260411_0016
Create Date: 2026-04-12 16:45:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260412_0017"
down_revision: str | None = "20260411_0016"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "character_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("external_location_id", sa.BigInteger(), nullable=True),
        sa.Column("resolved_location_id", sa.Integer(), nullable=True),
        sa.Column("location_name", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["esi_characters.id"]),
        sa.ForeignKeyConstraint(["resolved_location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["type_id"], ["items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("character_id", "type_id", "external_location_id"),
    )
    op.create_index(op.f("ix_character_assets_character_id"), "character_assets", ["character_id"], unique=False)
    op.create_index(
        op.f("ix_character_assets_external_location_id"),
        "character_assets",
        ["external_location_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_character_assets_resolved_location_id"),
        "character_assets",
        ["resolved_location_id"],
        unique=False,
    )
    op.create_index(op.f("ix_character_assets_type_id"), "character_assets", ["type_id"], unique=False)

    op.create_table(
        "character_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("volume_remain", sa.Integer(), nullable=False),
        sa.Column("is_buy_order", sa.Boolean(), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("external_location_id", sa.BigInteger(), nullable=True),
        sa.Column("resolved_location_id", sa.Integer(), nullable=True),
        sa.Column("issued", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["esi_characters.id"]),
        sa.ForeignKeyConstraint(["resolved_location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["type_id"], ["items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
    )
    op.create_index(op.f("ix_character_orders_character_id"), "character_orders", ["character_id"], unique=False)
    op.create_index(
        op.f("ix_character_orders_external_location_id"),
        "character_orders",
        ["external_location_id"],
        unique=False,
    )
    op.create_index(op.f("ix_character_orders_order_id"), "character_orders", ["order_id"], unique=False)
    op.create_index(
        op.f("ix_character_orders_resolved_location_id"),
        "character_orders",
        ["resolved_location_id"],
        unique=False,
    )
    op.create_index(op.f("ix_character_orders_type_id"), "character_orders", ["type_id"], unique=False)

    op.create_table(
        "in_transit_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_location_id", sa.Integer(), nullable=False),
        sa.Column("target_location_id", sa.Integer(), nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["target_location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["type_id"], ["items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_location_id", "target_location_id", "type_id"),
    )
    op.create_index(op.f("ix_in_transit_assets_source_location_id"), "in_transit_assets", ["source_location_id"], unique=False)
    op.create_index(op.f("ix_in_transit_assets_target_location_id"), "in_transit_assets", ["target_location_id"], unique=False)
    op.create_index(op.f("ix_in_transit_assets_type_id"), "in_transit_assets", ["type_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_in_transit_assets_type_id"), table_name="in_transit_assets")
    op.drop_index(op.f("ix_in_transit_assets_target_location_id"), table_name="in_transit_assets")
    op.drop_index(op.f("ix_in_transit_assets_source_location_id"), table_name="in_transit_assets")
    op.drop_table("in_transit_assets")

    op.drop_index(op.f("ix_character_orders_type_id"), table_name="character_orders")
    op.drop_index(op.f("ix_character_orders_resolved_location_id"), table_name="character_orders")
    op.drop_index(op.f("ix_character_orders_order_id"), table_name="character_orders")
    op.drop_index(op.f("ix_character_orders_external_location_id"), table_name="character_orders")
    op.drop_index(op.f("ix_character_orders_character_id"), table_name="character_orders")
    op.drop_table("character_orders")

    op.drop_index(op.f("ix_character_assets_type_id"), table_name="character_assets")
    op.drop_index(op.f("ix_character_assets_resolved_location_id"), table_name="character_assets")
    op.drop_index(op.f("ix_character_assets_external_location_id"), table_name="character_assets")
    op.drop_index(op.f("ix_character_assets_character_id"), table_name="character_assets")
    op.drop_table("character_assets")
