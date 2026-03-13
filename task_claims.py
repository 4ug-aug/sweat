import asyncio


class TaskClaims:
    _instance: "TaskClaims | None" = None

    def __init__(self):
        self._lock = asyncio.Lock()
        self._claimed: set[str] = set()

    @classmethod
    def get(cls) -> "TaskClaims":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def try_claim(self, gid: str) -> bool:
        async with self._lock:
            if gid in self._claimed:
                return False
            self._claimed.add(gid)
            return True

    async def release(self, gid: str) -> None:
        async with self._lock:
            self._claimed.discard(gid)

    async def is_claimed(self, gid: str) -> bool:
        async with self._lock:
            return gid in self._claimed
