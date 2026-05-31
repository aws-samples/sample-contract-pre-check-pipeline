"""SHA-256 and perceptual hash computation tools."""

import hashlib
import io

import imagehash
from PIL import Image
from strands import tool


@tool
def compute_sha256_hash(text_content: str) -> dict:
    """Compute SHA-256 hash of document text content.

    Args:
        text_content: The extracted text content of the document.

    Returns:
        A dict with the sha256_hash value.
    """
    hash_value = hashlib.sha256(text_content.encode("utf-8")).hexdigest()
    return {"sha256_hash": hash_value}


@tool
def compute_perceptual_hash(image_bytes: bytes) -> dict:
    """Compute perceptual hash (pHash) of a page image.

    Args:
        image_bytes: The raw image bytes.

    Returns:
        A dict with the phash hex string.
    """
    img = Image.open(io.BytesIO(image_bytes))
    phash = imagehash.phash(img)
    return {"phash": str(phash)}


def hamming_distance(hash1: str, hash2: str) -> int:
    """Compute Hamming distance between two hex hash strings."""
    h1 = int(hash1, 16)
    h2 = int(hash2, 16)
    return bin(h1 ^ h2).count("1")
