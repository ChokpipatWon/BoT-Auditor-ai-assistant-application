# config.py

class Config:
    gemini_api_key = None
    openai_api_key = None

    @staticmethod
    def set_gemini_key(key: str):
        Config.gemini_api_key = key

    @staticmethod
    def set_openai_key(key: str):
        Config.openai_api_key = key
