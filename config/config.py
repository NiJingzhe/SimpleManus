from SimpleLLMFunc import OpenAICompatible
from functools import lru_cache


current_file_dir = (
    __file__.rsplit("/", 1)[0] if "/" in __file__ else __file__.rsplit("\\", 1)[0]
)


class Config:

    JSON_FILE = current_file_dir + "/provider.json"
    INTERFACE_COLLECTION = OpenAICompatible.load_from_json_file(JSON_FILE)
    BASIC_INTERFACE = INTERFACE_COLLECTION["chatanywhere"]["claude-sonnet-4-20250514"]

    CODE_INTERFACE = INTERFACE_COLLECTION["chatanywhere"]["claude-sonnet-4-20250514"]

    REASONING_INTERFACE = INTERFACE_COLLECTION["chatanywhere"]["deepseek-v3"]

    QUICK_INTERFACE = INTERFACE_COLLECTION["chatanywhere"]["gemini-1.5-flash-latest"]


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Get the configuration instance."""
    return Config()
