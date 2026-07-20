"""Add source column + civic layer tables for multi-feed twin.

Revision ID: 0002_multisource
Revises: 0001_initial
Create Date: 2026-07-20

"""

from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "0002_multisource"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sensor_readings",
        sa.Column("source", sa.String(length=32), nullable=False, server_default="weather"),
    )
    op.create_index(
        "ix_sensor_readings_source_type",
        "sensor_readings",
        ["source", "reading_type"],
        unique=False,
    )

    op.create_table(
        "pathways",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="LINESTRING",
                srid=4326,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pathways_geometry",
        "pathways",
        ["geometry"],
        unique=False,
        postgresql_using="gist",
    )

    op.create_table(
        "amenities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column("amenity_type", sa.String(length=64), nullable=False),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_amenities_geometry",
        "amenities",
        ["geometry"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index("ix_amenities_type", "amenities", ["amenity_type"], unique=False)

    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id", name="uq_incidents_external_id"),
    )
    op.create_index(
        "ix_incidents_geometry",
        "incidents",
        ["geometry"],
        unique=False,
        postgresql_using="gist",
    )


def downgrade() -> None:
    op.drop_index("ix_incidents_geometry", table_name="incidents", postgresql_using="gist")
    op.drop_table("incidents")
    op.drop_index("ix_amenities_type", table_name="amenities")
    op.drop_index("ix_amenities_geometry", table_name="amenities", postgresql_using="gist")
    op.drop_table("amenities")
    op.drop_index("ix_pathways_geometry", table_name="pathways", postgresql_using="gist")
    op.drop_table("pathways")
    op.drop_index("ix_sensor_readings_source_type", table_name="sensor_readings")
    op.drop_column("sensor_readings", "source")
