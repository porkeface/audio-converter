"""
Key extraction module for mflac files.

Provides tools to extract and analyze the key stream used for decryption.
"""
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# mflac header size
MFLAC_HEADER_SIZE = 192


class KeyExtractor:
    """
    Extracts key stream from mflac files.

    The key stream can be extracted if you have:
    1. An mflac file and its decrypted FLAC version (known plaintext attack)
    2. Or by analyzing the file structure
    """

    def __init__(self) -> None:
        self._key_stream: Optional[bytes] = None

    def extract_from_pair(self, mflac_path: str, flac_path: str) -> bytes:
        """
        Extract key stream by XORing mflac encrypted data with known FLAC plaintext.

        Args:
            mflac_path: Path to encrypted mflac file
            flac_path: Path to decrypted FLAC file

        Returns:
            Key stream bytes
        """
        logger.info(f"Extracting key from: {mflac_path} and {flac_path}")

        with open(mflac_path, 'rb') as f:
            mflac_data = f.read()
        with open(flac_path, 'rb') as f:
            flac_data = f.read()

        # Skip mflac header
        encrypted = mflac_data[MFLAC_HEADER_SIZE:]

        # Key stream = encrypted XOR plaintext
        min_len = min(len(encrypted), len(flac_data))
        if len(encrypted) != len(flac_data):
            logger.warning(
                f"Size mismatch: encrypted={len(encrypted)}, flac={len(flac_data)}. "
                f"Using min length: {min_len}"
            )

        key_stream = bytearray(min_len)
        for i in range(min_len):
            key_stream[i] = encrypted[i] ^ flac_data[i]

        self._key_stream = bytes(key_stream)
        logger.info(f"Extracted key stream: {len(self._key_stream):,} bytes")
        return self._key_stream

    def save_key(self, output_path: str) -> None:
        """Save extracted key stream to file."""
        if self._key_stream is None:
            raise ValueError("No key stream extracted yet")
        with open(output_path, 'wb') as f:
            f.write(self._key_stream)
        logger.info(f"Key saved to: {output_path}")

    def load_key(self, input_path: str) -> bytes:
        """Load key stream from file."""
        with open(input_path, 'rb') as f:
            self._key_stream = f.read()
        logger.info(f"Key loaded from: {input_path} ({len(self._key_stream):,} bytes)")
        return self._key_stream

    def analyze_key(self, num_bytes: int = 1024) -> dict:
        """
        Analyze the key stream to understand its structure.

        Returns:
            Dictionary with analysis results
        """
        if self._key_stream is None:
            raise ValueError("No key stream extracted yet")

        sample = self._key_stream[:num_bytes]

        # Byte value distribution
        counts = [0] * 256
        for b in sample:
            counts[b] += 1
        unique_bytes = sum(1 for c in counts if c > 0)

        # Check for periodicity
        period = self._find_period(sample)

        return {
            'length': len(self._key_stream),
            'unique_bytes_in_sample': unique_bytes,
            'sample_size': len(sample),
            'period': period,
            'first_64_bytes': self._key_stream[:64].hex(),
        }

    @staticmethod
    def _find_period(data: bytes, max_period: int = 1024) -> int:
        """Find period of data if it exists."""
        for period in range(1, min(max_period, len(data) // 2)):
            is_periodic = True
            for i in range(period, min(len(data), max_period * 2)):
                if data[i] != data[i % period]:
                    is_periodic = False
                    break
            if is_periodic:
                return period
        return len(data)  # No period found
