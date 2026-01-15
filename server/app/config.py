from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NCS Document Verifier"
    debug: bool = False
    secret_key: str = "change-me"
    allowed_origins: str = "*"
    data_dir: str = "server/data"
    database_path: str = "server/data/ncs_verifier.db"
    tesseract_cmd: str | None = None
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", env_prefix="NCS_")


settings = Settings()
