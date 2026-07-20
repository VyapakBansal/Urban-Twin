"""initial postgis schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-20

"""

from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "buildings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "geometry",
            # spatial_index=False: GeoAlchemy2 otherwise auto-creates the GiST index
            geoalchemy2.types.Geometry(
                geometry_type="POLYGON",
                srid=4326,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=False,
        ),
        sa.Column("height", sa.Float(), nullable=True),
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
        "idx_buildings_geometry",
        "buildings",
        ["geometry"],
        unique=False,
        postgresql_using="gist",
    )

    op.create_table(
        "neighborhood_bounds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="POLYGON",
                srid=4326,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_neighborhood_bounds_geometry",
        "neighborhood_bounds",
        ["geometry"],
        unique=False,
        postgresql_using="gist",
    )

    op.create_table(
        "sensor_readings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("station_id", sa.String(length=64), nullable=False),
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
        sa.Column("reading_type", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sensor_readings_geometry",
        "sensor_readings",
        ["geometry"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index(
        "ix_sensor_readings_recorded_at",
        "sensor_readings",
        ["recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_sensor_readings_station_recorded",
        "sensor_readings",
        ["station_id", "recorded_at"],
        unique=False,
    )

    op.create_table(
        "forecasts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("station_id", sa.String(length=64), nullable=False),
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
        sa.Column("reading_type", sa.String(length=32), nullable=False),
        sa.Column("predicted_value", sa.Float(), nullable=False),
        sa.Column("target_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_forecasts_geometry",
        "forecasts",
        ["geometry"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index(
        "ix_forecasts_station_target",
        "forecasts",
        ["station_id", "target_time"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_forecasts_station_target", table_name="forecasts")
    op.drop_index("ix_forecasts_geometry", table_name="forecasts", postgresql_using="gist")
    op.drop_table("forecasts")

    op.drop_index(
        "ix_sensor_readings_station_recorded", table_name="sensor_readings"
    )
    op.drop_index("ix_sensor_readings_recorded_at", table_name="sensor_readings")
    op.drop_index(
        "ix_sensor_readings_geometry",
        table_name="sensor_readings",
        postgresql_using="gist",
    )
    op.drop_table("sensor_readings")

    op.drop_index(
        "idx_neighborhood_bounds_geometry",
        table_name="neighborhood_bounds",
        postgresql_using="gist",
    )
    op.drop_table("neighborhood_bounds")

    op.drop_index(
        "idx_buildings_geometry", table_name="buildings", postgresql_using="gist"
    )
    op.drop_table("buildings")
