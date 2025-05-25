from dotenv import load_dotenv
from openai import OpenAI
from typing import List, Dict, Optional
from utils import logger
import os

load_dotenv()

class LLMClient:
    DEFAULT_MODEL: str = "mistralai/mistral-small-3.1-24b-instruct:free"
    DEFAULT_BASE_URL: str = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        self.api_key = api_key if api_key is not None else os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            logger.error("API key is missing. Please provide it as an argument or set OPENROUTER_API_KEY.")
            raise ValueError("API key must be provided or set as OPENROUTER_API_KEY in environment variables.")

        self.model_name = model_name if model_name is not None else self.DEFAULT_MODEL
        self.base_url = base_url if base_url is not None else self.DEFAULT_BASE_URL

        try:
            self.client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
            )
            logger.info(f"LLMClient initialized with model: {self.model_name}, base_url: {self.base_url}")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
            raise

    def get_response(self, messages) -> Optional[str]:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages
            )
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                logger.debug(f"Received response from {self.model_name}: {content}")
                return content
            else:
                logger.warning(f"Received no valid choices or message content from {self.model_name}.")
        except Exception as e:
            logger.error(f"An unexpected error occurred while calling LLM API ({self.model_name}): {e}", exc_info=True)

        return None