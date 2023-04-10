import json
import logging
import time
from typing import Tuple, Optional, Dict

from pika import BlockingConnection
from redis import Redis

from common.constants import RESULT_EXCHANGE_NAME
from common.meteo_data import Results, MeteoEncoder
from common.store_strategy import StoreStrategy, SortedSetStoreStrategy

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_INTERVAL = 2000
STARTUP_DELAY = 5


class TumblingWindow:
    def __init__(
            self,
            redis: Redis,
            rabbitmq: BlockingConnection,
            interval: Optional[int] = None,
            store_strategy: Optional[StoreStrategy] = None,
            exchange_name: Optional[str] = None,
    ):
        logger.info("Initializing TumblingWindow")
        self._interval = interval or DEFAULT_WINDOW_INTERVAL
        self._store = store_strategy or SortedSetStoreStrategy(redis)
        self._rabbitmq = rabbitmq
        self._exchange_name = exchange_name or RESULT_EXCHANGE_NAME
        self._channel = rabbitmq.channel()
        self._channel.exchange_declare(exchange=self._exchange_name, exchange_type='fanout')

    def run(self):
        logger.info("Starting TumblingWindow")
        last_time = time.time()
        time.sleep(STARTUP_DELAY)
        while True:
            time.sleep(self._interval / 1000)
            end = last_time + self._interval / 1000
            assert end <= time.time()
            logger.debug(f"Running tumbling window from {last_time} to {end}")
            wellness_data, wellness_timestamp = self._get_data('wellness', last_time, end)
            pollution_data, pollution_timestamp = self._get_data('pollution', last_time, end)
            results = Results(
                wellness_data=wellness_data,
                wellness_timestamp=wellness_timestamp,
                pollution_data=pollution_data,
                pollution_timestamp=pollution_timestamp,
            )
            self._send_results(results)


    def _send_results(self, results: Results):
        logger.debug(f"Sending results to exchange {self._exchange_name}")
        self._channel.basic_publish(
            exchange=self._exchange_name,
            routing_key='',
            body=json.dumps(results, cls=MeteoEncoder).encode('utf-8')
        )

    def _get_data(self, key: str, start: float, end: float) -> Tuple[float, float]:
        res = self._store.get(key, start, end)
        logger.debug(f"Got data from redis for key {key}: {res}")
        # returns a lis of tuples (key, score) where key is the value and score is the timestamp
        if not res or len(res) == 0:
            return 0, 0
        last_time = max(res, key=lambda x: x[1])[1]
        mean = sum([float(x[0]) for x in res]) / len(res)
        logger.debug(f"Computed mean {mean} for key {key} from {start} to {end} with last time {last_time}")
        return mean, last_time
