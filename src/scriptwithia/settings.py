from pydantic_settings import SettingsConfigDict, BaseSettings

class Settings(BaseSettings):
    GROQ_API_KEY: str

    model_config=SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        env_file_depth=1,
        extra="ignore"
        )

settings = Settings()

