from abc import abstractmethod, ABC
from typing import List, Tuple

from redis.asyncio import Redis


class StoreStrategy(ABC):
    @abstractmethod
    async def store(self, key: str, timestamp_ns: int, value: float) -> int:
        pass

    @abstractmethod
    async def get(self, key: str, start: float, end: float) -> List[Tuple[float, float]]:
        pass


class SortedSetStoreStrategy(StoreStrategy):
    def __init__(self, redis: Redis):
        self._redis = redis

    async def store(self, key: str, timestamp_ns: int, value: float) -> int:
        # add the timestamp to the value to make it unique
        return await self._redis.zadd(key, {f"{value}:{timestamp_ns}": timestamp_ns / 1e9})

    async def get(self, key: str, start: float, end: float) -> List[Tuple[float, float]]:
        res = await self._redis.zrange(key, start, end, byscore=True, withscores=True)
        return [(float(x.split(b':')[0]), y) for x, y in res]


class TimeSeriesStoreStrategy(StoreStrategy):
    def __init__(self, redis: Redis):
        self._ts = redis.ts()

    async def store(self, key: str, timestamp_ns: int, value: float) -> int:
        return await self._ts.add(key, int(timestamp_ns / 1e6), value)

    async def get(self, key: str, start: float, end: float) -> List[Tuple[float, float]]:
        start, end = int(start * 1e3), int(end * 1e3)  # convert to milliseconds
        res = await self._ts.range(key, start, end)
        return [(float(x[1]), x[0]) for x in res]
