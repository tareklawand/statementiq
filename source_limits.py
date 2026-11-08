"""Stop oversized external bodies before buffering them on the free server."""
import json
import time
import threading

MAX_FACTS_BYTES = 24 * 1024 * 1024
MAX_FILING_BYTES = 50 * 1024 * 1024
_JSON_READ_LOCK = threading.Lock()


def read_bounded(response, max_bytes, max_seconds=45):
    """Count decoded stream bytes; Content-Length alone can be compressed/wrong."""
    started = time.monotonic()
    try:
        response.raise_for_status()
        declared = response.headers.get("Content-Length")
        if declared and declared.isdigit() and int(declared) > max_bytes:
            raise ValueError("Source document exceeds the automated review size limit.")
        content = bytearray()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if time.monotonic() - started > max_seconds:
                raise TimeoutError("Source document download exceeded its processing budget.")
            if len(content) + len(chunk) > max_bytes:
                raise ValueError("Source document exceeds the automated review size limit.")
            content.extend(chunk)
        return content
    finally:
        response.close()


def read_json(response):
    # Company Facts contains many years of concepts before the caller filters
    # them. Do not decode multiple full histories concurrently on 512 MB.
    with _JSON_READ_LOCK:
        return json.loads(read_bounded(response, MAX_FACTS_BYTES))
