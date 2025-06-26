from SimpleLLMFunc import OpenAICompatible
from functools import lru_cache


current_file_dir = (
    __file__.rsplit("/", 1)[0] if "/" in __file__ else __file__.rsplit("\\", 1)[0]
)


class Config:

    JSON_FILE = current_file_dir + "/provider.json"
    INTERFACE_COLLECTION = OpenAICompatible.load_from_json_file(JSON_FILE)

    BASIC_INTERFACE = INTERFACE_COLLECTION["chatanywhere"]["gpt-4o"]
    #BASIC_INTERFACE = INTERFACE_COLLECTION["chatanywhere"]["gemini-2.5-pro-preview-06-05"]
    #BASIC_INTERFACE = INTERFACE_COLLECTION["chatanywhere"]["gemini-2.5-flash"]

    CODE_INTERFACE = INTERFACE_COLLECTION["chatanywhere"]["claude-sonnet-4-20250514"]

    REASONING_INTERFACE = INTERFACE_COLLECTION["chatanywhere"]["deepseek-v3"]

    QUICK_INTERFACE = INTERFACE_COLLECTION["chatanywhere"]["gemini-2.5-flash"]


@lru_cache()
def get_config() -> Config:
    """Get the configuration instance."""
    return Config()
