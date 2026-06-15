import threading
from functools import lru_cache
from core.logging_config import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._model = None
        self._model_lock = threading.Lock()
        self._cache_hits = 0
        self._cache_misses = 0

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _get_model(self):
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    logger.info("Lazy-loading SentenceTransformer model: all-MiniLM-L6-v2")
                    from sentence_transformers import SentenceTransformer
                    self._model = SentenceTransformer('all-MiniLM-L6-v2')
        return self._model

    def encode(self, text: str) -> list[float]:
        """Encodes a string into a float32 vector. Results are cached (LRU, 512 entries)."""
        return self._cached_encode(text)

    @lru_cache(maxsize=512)
    def _cached_encode(self, text: str) -> list[float]:
        """Internal cached encode — identical strings skip the model entirely."""
        model = self._get_model()
        return model.encode(text).tolist()

    def cache_info(self) -> dict:
        """Return cache stats for monitoring."""
        info = self._cached_encode.cache_info()
        return {
            "hits": info.hits,
            "misses": info.misses,
            "maxsize": info.maxsize,
            "currsize": info.currsize,
        }


def get_embedding(text: str) -> list[float]:
    """Helper method to encode text from the singleton."""
    return EmbeddingService.get_instance().encode(text)

