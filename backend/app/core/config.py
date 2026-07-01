from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    APP_NAME: str = "ProcureGPT"
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "admin"
    MYSQL_DATABASE: str = "procuregpt"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "ProcureGPT"

    IMAP_HOST: str = "imap.gmail.com"
    IMAP_PORT: int = 993
    IMAP_USER: str = ""
    IMAP_PASSWORD: str = ""

    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 25

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
