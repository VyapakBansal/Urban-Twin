from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://urban:urban@localhost:5433/urban_twin"
    database_url_sync: str = "postgresql+psycopg://urban:urban@localhost:5433/urban_twin"

    aoi_name: str = "Kensington Calgary"
    aoi_min_lon: float = -114.100
    aoi_min_lat: float = 51.048
    aoi_max_lon: float = -114.062
    aoi_max_lat: float = 51.062

    station_id: str = "calgary-kensington-1"
    station_lat: float = 51.053
    station_lon: float = -114.081

    openweather_api_key: str = ""
    ingestion_poll_interval_sec: int = 300

    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_sensor_readings: str = "sensor.readings"
    kafka_topic_forecasts: str = "forecasts.generated"
    kafka_topic_drone_telemetry: str = "drone.telemetry"
    kafka_topic_drone_control: str = "drone.control"

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_rate_limit: str = "60/minute"
    # Comma-separated browser origins (Azure nginx same-origin can list the public http://IP)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    ws_bridge_host: str = "127.0.0.1"
    ws_bridge_port: int = 8001

    # PX4 / MAVSDK drone bridge. The fixed home anchors PX4 local NED to WGS84.
    drone_system_address: str = "udp://:14540"
    drone_id: str = "px4-sitl-1"
    drone_home_lat: float = 51.053
    drone_home_lon: float = -114.081
    drone_home_alt_m: float = 1045.0
    drone_telemetry_hz: float = 20.0
    drone_control_hz: float = 20.0
    drone_command_timeout_sec: float = 0.5
    drone_max_horizontal_speed_m_s: float = 5.0
    drone_max_vertical_speed_m_s: float = 2.0
    drone_max_yaw_rate_deg_s: float = 60.0
    drone_min_altitude_m: float = 2.0
    drone_max_altitude_m: float = 120.0

    forecast_horizon_hours: int = 24
    forecast_horizons: str = "1,2,3,6,12,24,48"
    forecast_interval_sec: int = 900
    forecast_model_version: str = "lgbm-mh-v1"
    forecast_reading_type: str = "temp"
    forecast_targets: str = "temp,river_level,aqi_pm25"
    forecast_train_days: int = 1826  # ~5 years
    forecast_model_dir: str = "models"

    # Multi-source feeds
    openaq_api_key: str = ""
    river_station_id: str = "05BH004"
    ingest_sources: str = "weather,river,air,incidents,pathways,amenities"

    # Supabase / cloud (optional — same Postgres protocol as local Docker)
    supabase_url: str = ""
    supabase_anon_key: str = ""

    @property
    def aoi_bbox(self) -> tuple[float, float, float, float]:
        """(min_lon, min_lat, max_lon, max_lat) in WGS84."""
        return (
            self.aoi_min_lon,
            self.aoi_min_lat,
            self.aoi_max_lon,
            self.aoi_max_lat,
        )

    @property
    def ingest_source_list(self) -> list[str]:
        return [s.strip() for s in self.ingest_sources.split(",") if s.strip()]

    @property
    def forecast_target_list(self) -> list[str]:
        return [s.strip() for s in self.forecast_targets.split(",") if s.strip()]

    @property
    def forecast_horizon_list(self) -> list[int]:
        return [int(x.strip()) for x in self.forecast_horizons.split(",") if x.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [s.strip() for s in self.cors_origins.split(",") if s.strip()]


settings = Settings()
