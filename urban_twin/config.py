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

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_rate_limit: str = "60/minute"

    forecast_horizon_hours: int = 1
    forecast_interval_sec: int = 900
    forecast_model_version: str = "persistence-v1"
    forecast_reading_type: str = "temp"

    @property
    def aoi_bbox(self) -> tuple[float, float, float, float]:
        """(min_lon, min_lat, max_lon, max_lat) in WGS84."""
        return (
            self.aoi_min_lon,
            self.aoi_min_lat,
            self.aoi_max_lon,
            self.aoi_max_lat,
        )


settings = Settings()
