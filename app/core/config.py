from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # DeepSeek LLM
    deepseek_api_key: str
    deepseek_api_base: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # PaddleOCR HTTP API
    paddle_ocr_api_url: str
    paddle_ocr_api_key: str = ""
    paddle_ocr_model: str = "paddle-ocr"

    # MySQL（完整 SQLAlchemy 连接串）
    database_url: str


settings = Settings()
