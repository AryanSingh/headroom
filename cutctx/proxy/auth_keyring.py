import logging
import os

try:
    import keyring
except ImportError:
    keyring = None

logger = logging.getLogger(__name__)

def get_api_key(provider: str) -> str:
    """
    Retrieve the API key for a given provider.
    Priority:
    1. Environment variable (e.g., OPENAI_API_KEY)
    2. OS Keyring (Windows Credential Manager / Linux Secret Service / macOS Keychain)

    Args:
        provider: 'openai', 'anthropic', 'gemini', etc.
    """
    env_var_name = f"{provider.upper()}_API_KEY"

    # 1. Check environment variable
    api_key = os.environ.get(env_var_name, "").strip()
    if api_key:
        return api_key

    # 2. Check OS Keyring
    if keyring is not None:
        try:
            # We store the credentials under the service name 'cutctx'
            key = keyring.get_password("cutctx", env_var_name)
            if key:
                logger.debug(f"Retrieved {env_var_name} from OS keyring")
                return key.strip()
        except Exception as e:
            logger.warning(f"Failed to read from OS keyring for {env_var_name}: {e}")

    return ""
