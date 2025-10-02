import logging
from .base_api import AITranslator, FooAITranslator, prompt
from .openai_style import OpenAITranslator
from .openai_style_free import OpenAIFreeTranslator
logger = logging.getLogger(__name__)

def get_translator(translator_type: str) -> AITranslator:
    if translator_type == "foo":
        return FooAITranslator()
    elif translator_type == "openai":
        return OpenAITranslator(prompt)
    elif translator_type == "free":
        return OpenAIFreeTranslator(prompt)
    else:
        raise ValueError("Unsupported translator type")