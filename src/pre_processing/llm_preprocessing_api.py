from openai import OpenAI
import logging

from config import DOUBAO_API_KEY, DOUBAO_POD

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Load Doubao API configuration
try:
    doubao_api_key = DOUBAO_API_KEY
    doubao_base_url = "https://ark.cn-beijing.volces.com/api/v3"
    model_pod = DOUBAO_POD

    # Initialize Doubao client
    client = OpenAI(
        api_key=doubao_api_key,
        base_url=doubao_base_url
    )
except Exception as e:
    logger.critical(f"Failed to initialize Doubao client: {e}")
    client = None


def call_doubao_api(
        messages,
        max_tokens=500,
        temperature=0.1,
        model=None
):
    """
    Call Doubao API with configurable parameters

    Args:
        messages (list): Conversation messages
        max_tokens (int): Maximum token generation limit
        temperature (float): Sampling temperature for generation
        model (str, optional): Specific model endpoint

    Returns:
        str: Generated API response content
    """
    if client is None:
        raise RuntimeError("Doubao client not initialized")

    try:
        # Use default model if not specified
        model = model or model_pod

        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        response = completion.choices[0].message.content

        # Optional logging for debugging
        logger.info(f"API Response generated (Tokens: {len(response.split())})")

        return response

    except Exception as e:
        logger.error(f"Doubao API call failed: {e}")
        raise