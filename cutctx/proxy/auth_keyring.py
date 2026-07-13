import logging
import os
from collections.abc import MutableMapping

try:
    import keyring
except ImportError:
    keyring = None

logger = logging.getLogger(__name__)


_UPSTREAM_ENV_ALIASES: dict[str, tuple[str, ...]] = {
    # These names are documented in .env.example.  Keep the provider-native
    # variables as the preferred, cross-client contract, while accepting the
    # documented Cutctx aliases so a copied sample configuration works.
    "openai": ("CUTCTX_UPSTREAM_OPENAI_API_KEY",),
    "anthropic": ("CUTCTX_UPSTREAM_ANTHROPIC_API_KEY",),
    # Google is the provider name used in configuration; Gemini is the name
    # used by the proxy's auth lookup.
    "gemini": ("CUTCTX_UPSTREAM_GOOGLE_API_KEY",),
    "google": ("CUTCTX_UPSTREAM_GOOGLE_API_KEY",),
    "bedrock": ("CUTCTX_UPSTREAM_BEDROCK_API_KEY",),
}


def inject_provider_authorization(headers: MutableMapping[str, str], provider: str) -> bool:
    """Add a configured provider credential when a client sent none.

    The proxy must not replace a caller-supplied credential: clients often
    intentionally route different requests to different provider accounts.
    Returns ``True`` only when this helper added the Authorization header.
    """
    if any(name.lower() == "authorization" for name in headers):
        return False

    api_key = get_api_key(provider)
    if not api_key:
        return False

    headers["Authorization"] = f"Bearer {api_key}"
    return True


def get_api_key(provider: str) -> str:
    """
    Retrieve the API key for a given provider.
    Priority:
    1. Provider environment variable (e.g., OPENAI_API_KEY)
    2. Documented Cutctx compatibility alias (e.g., CUTCTX_UPSTREAM_OPENAI_API_KEY)
    3. OS Keyring (Windows Credential Manager / Linux Secret Service / macOS Keychain)

    Args:
        provider: 'openai', 'anthropic', 'gemini', etc.
    """
    env_var_name = f"{provider.upper()}_API_KEY"

    # 1. Check environment variable
    api_key = os.environ.get(env_var_name, "").strip()
    if api_key:
        return api_key

    # .env.example has historically documented CUTCTX_UPSTREAM_* names while
    # runtime clients and SDKs use provider-native names.  Prefer the native
    # name above, but make the documented configuration functional.
    for alias in _UPSTREAM_ENV_ALIASES.get(provider.lower(), ()):
        api_key = os.environ.get(alias, "").strip()
        if api_key:
            return api_key

    # 3. Check OS Keyring
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
