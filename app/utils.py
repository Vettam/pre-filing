import unicodedata
import re
from urllib.parse import urlparse, urlunparse, quote
from app.constants import UPLOAD_TIMESTAMP_REGEX


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


def remove_timestamp_from_storage_filename(filename: str) -> str:
    """
    Input: test_2025-12-01T04-07-03-485626-00-00.pdf
    Output: test.pdf
    """
    match = re.match(UPLOAD_TIMESTAMP_REGEX, filename)
    if match:
        return f"{match.group(1)}{match.group(2)}"
    return filename


def parse_label_to_int(label: str | None) -> int | None:
    """
    Parse a page label string to its numeric component.
    Examples:
      "5"   -> 5
      "A3"  -> 3
      "NS2" -> 2
      "iv"  -> 4  (roman)
      "A"   -> None (alpha_only — no numeric part)
      None  -> None
    """
    if not label:
        return None
 
    # Pure integer
    try:
        return int(label)
    except ValueError:
        pass
 
    # Roman numerals
    roman_map = {
        "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
        "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
        "xi": 11, "xii": 12, "xiii": 13, "xiv": 14, "xv": 15,
        "xvi": 16, "xvii": 17, "xviii": 18, "xix": 19, "xx": 20,
    }
    if label.lower() in roman_map:
        return roman_map[label.lower()]
 
    # alpha_numeric: extract trailing number e.g. A3 -> 3, NS12 -> 12
    match = re.match(r'^[A-Za-z]+(\d+)$', label)
    if match:
        return int(match.group(1))
 
    # alpha_only like "A", "B", "NS" — no numeric part
    return None


def compute_expected_pages(
    start_label: str | None,
    end_label: str | None,
    style: str | None,
) -> int | None:
    """
    Compute expected page count from start and end labels.
    Returns None if validation should be skipped for this style.
    """
    if style in ("alpha_only", "none", None):
        return None  # skip validation
 
    start_num = parse_label_to_int(start_label)
    end_num   = parse_label_to_int(end_label)
 
    if start_num is None:
        return None  # can't compute
 
    # If end is missing or same as start, it's a single page
    if end_num is None or end_num == start_num:
        return 1
 
    return end_num - start_num + 1


def extract_alpha_prefix(label: str | None) -> str | None:
    """Extract alpha prefix from a label. 'A3' -> 'A', 'NS2' -> 'NS', '5' -> None"""
    if not label:
        return None
    match = re.match(r'^([A-Za-z]+)\d+$', label)
    if match:
        return match.group(1)
    return None


def to_roman(n: int) -> str:
    vals = [
        (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"),
        (100,  "c"), (90,  "xc"), (50,  "l"), (40,  "xl"),
        (10,   "x"), (9,   "ix"), (5,   "v"), (4,   "iv"), (1, "i")
    ]
    result = ""
    for v, s in vals:
        while n >= v:
            result += s
            n -= v
    return result


def compute_end_label(start_label: str, actual_pages: int, style: str) -> str | None:
    """
    Given a start label and actual page count, compute the correct end label
    in the same style.
 
    numeric:       "5"  + 10 pages -> "14"
    alpha_numeric: "A1" + 10 pages -> "A10"
    roman:         "iv" + 10 pages -> "xiii"
    alpha_only:    skip (return None)
    none:          skip (return None)
    """
    if style in ("alpha_only", "none", None):
        return None
 
    start_num = parse_label_to_int(start_label)
    if start_num is None:
        return None
 
    end_num = start_num + actual_pages - 1
 
    if style == "numeric":
        return str(end_num)
 
    if style == "roman":
        return to_roman(end_num)
 
    if style == "alpha_numeric":
        prefix = extract_alpha_prefix(start_label)
        if not prefix:
            return None
        return f"{prefix}{end_num}"
 
    return None
