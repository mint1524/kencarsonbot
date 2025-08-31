from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_IDS: str = ""
    DATABASE_URL: str
    REDIS_URL: str
    WEBHOOK_HOST: str = ""
    WEBHOOK_PATH: str = "/bot/webhook"
    PAYMENT_PROVIDER: str = "cryptobot"
    PLATFORM_USER_ID: int

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def admin_ids(self) -> set[int]:
        return set(int(x) for x in self.ADMIN_IDS.split(",") if x)

settings = Settings()
