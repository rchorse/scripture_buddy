from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    user_pool_id: str = ""
    user_pool_client_id: str = ""
    aws_region: str = "us-west-2"
    db_name: str = "scripturebuddy"


settings = Settings()
