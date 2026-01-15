from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NCS Verifier Service"
    debug: bool = False
    data_dir: str = "backend/ncs_verifier_service/data"
    database_path: str = "backend/ncs_verifier_service/data/verifier.db"
    tesseract_cmd: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_prefix="NCS_VERIFIER_")


settings = Settings()
