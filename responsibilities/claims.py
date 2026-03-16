import asyncio


class ResponsibilityClaims:
    _instance: "ResponsibilityClaims | None" = None

    def __init__(self):
        self._lock = asyncio.Lock()
        self._claimed: set[str] = set()

    @classmethod
    def get(cls) -> "ResponsibilityClaims":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def try_claim(self, event_key: str) -> bool:
        async with self._lock:
            if event_key in self._claimed:
                return False
            self._claimed.add(event_key)
            return True

    async def release(self, event_key: str) -> None:
        async with self._lock:
            self._claimed.discard(event_key)

    async def is_claimed(self, event_key: str) -> bool:
        async with self._lock:
            return event_key in self._claimed
