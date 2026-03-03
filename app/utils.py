import unicodedata
import re
from urllib.parse import urlparse, urlunparse, quote


def normalize_supabase_storage_key(text: str) -> str:
    # Replace en dash and em dash with regular hyphen
    text = text.replace("–", "-").replace("—", "-")

    # Normalize Unicode to remove accents and convert special characters
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")

    # Replace all characters not allowed by Supabase regex with underscore
    return re.sub(r"[^\w\/!.\-\*'() &@$=;:+,?]", "_", text)


def encode_url_path(url: str) -> str:
    """
    Encode the path part of a URL, leaving other parts (scheme, netloc, query, fragment) intact.

    Args:
        url (str): The original URL possibly containing spaces or unsafe characters in the path.

    Returns:
        str: The URL with the path percent-encoded.
    """
    parsed = urlparse(url)
    encoded_path = quote(parsed.path, safe="/")
    encoded_url = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            encoded_path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )
    return encoded_url
