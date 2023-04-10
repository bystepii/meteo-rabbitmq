import asyncio
import json
import logging
import os
from asyncio import AbstractEventLoop
from json import JSONDecodeError
from typing import Optional

from pika import BlockingConnection, SelectConnection, URLParameters
from pika.adapters.asyncio_connection import AsyncioConnection
from pika.channel import Channel
from pika.spec import Basic, BasicProperties
from redis.asyncio import Redis

from common.constants import PROCESSING_QUEUE_NAME
from common.meteo_data import RawMeteoData, RawPollutionData, MeteoDecoder
from common.meteo_utils import MeteoDataProcessor
from common.store_strategy import StoreStrategy, SortedSetStoreStrategy

logger = logging.getLogger(__name__)


class Server:
    def __init__(
            self,
            processor: MeteoDataProcessor,
            redis: Redis,
            rabbitmq_address: str,
            store_strategy: Optional[StoreStrategy] = None,
            queue_name: Optional[str] = None,
            prefetch_count: Optional[int] = None,
    ):
        logger.info("Initializing Server")
        self._processor = processor
        self._store = store_strategy or SortedSetStoreStrategy(redis)
        self._rabbitmq_address = rabbitmq_address
        self._connection: Optional[AsyncioConnection] = None
        self._ioloop: Optional[AbstractEventLoop] = None
        self._queue_name = queue_name or PROCESSING_QUEUE_NAME
        self._prefetch_count = prefetch_count or min(32, ((os.cpu_count() or 1) + 4) * 2)
        self._channel: Optional[Channel] = None
        self._consumer_tag: Optional[str] = None
        self._closing = False
        self._consuming = False

    def run(self):
        logger.info("Starting server")
        self._connect()
        self._ioloop.run_forever()

    def stop(self):
        if not self._closing:
            logger.info("Stopping server")
            self._closing = True
            if self._consuming:
                self._stop_consuming()
                self._ioloop.run_forever()
            else:
                self._ioloop.stop()
            logger.info("Server stopped")

    def _connect(self):
        logger.info(f"Connecting to RabbitMQ at {self._rabbitmq_address}")
        self._connection = AsyncioConnection(
            parameters=URLParameters(self._rabbitmq_address),
            on_open_callback=self._on_connection_open,
            on_open_error_callback=self._on_connection_open_error,
            on_close_callback=self._on_connection_close
        )
        self._ioloop = self._connection.ioloop

    def _close_connection(self):
        logger.info("Closing connection")
        self._consuming = False
        if self._connection.is_closing or self._connection.is_closed:
            logger.info("Connection is closing or already closed")
        else:
            logger.info("Closing connection")
            self._connection.close()

    def _on_connection_open(self, connection: SelectConnection):
        logger.info("Connected to RabbitMQ")
        logger.info("Opening channel")
        connection.channel(on_open_callback=self._on_channel_open)

    def _on_connection_open_error(self, connection: BlockingConnection, error: Exception):
        logger.error(f"Failed to connect to RabbitMQ: {error}")
        self._ioloop.stop()

    def _on_connection_close(self, connection: SelectConnection, reason: Exception):
        logger.info(f"Connection closed: {reason}")
        self._channel = None
        if self._closing:
            self._ioloop.stop()

    def _on_channel_open(self, channel: Channel):
        logger.info("Channel opened")
        self._channel = channel
        self._channel.add_on_close_callback(self._on_channel_close)
        logger.info(f"Declaring queue {self._queue_name}")
        self._channel.queue_declare(queue=self._queue_name, callback=self._on_queue_declared)

    def _on_channel_close(self, channel: Channel, reason: Exception):
        logger.info(f"Channel closed: {reason}")
        self._connection.close()

    def _on_queue_declared(self, frame):
        logger.info(f"Queue {self._queue_name} declared")
        self._set_qos()

    def _set_qos(self):
        logger.info(f"Setting QoS to {self._prefetch_count}")
        self._channel.basic_qos(prefetch_count=self._prefetch_count, callback=lambda _: self._start_consuming())

    def _start_consuming(self):
        logger.info("Starting consuming")
        self._channel.add_on_cancel_callback(self._on_consumer_cancelled)
        self._consumer_tag = self._channel.basic_consume(self._queue_name, self._on_message)
        self._consuming = True

    def _on_consumer_cancelled(self, method_frame):
        logger.info(f"Consumer cancelled: {method_frame}")
        if self._channel:
            self._channel.close()

    def _on_message(
            self,
            channel: Channel,
            method: Basic.Deliver,
            properties: BasicProperties,
            body: bytes
    ):
        logger.debug(f"Received message #{method.delivery_tag} from {properties.app_id}: {body}")
        try:
            raw_meteo_data = json.loads(body, cls=MeteoDecoder)
        except JSONDecodeError as e:
            logger.warning(f"Failed to decode message {body}: {e}")
            self._ack_message(method.delivery_tag)
            return
        if isinstance(raw_meteo_data, RawMeteoData):
            asyncio.create_task(self._process_meteo_data(raw_meteo_data, method.delivery_tag))
        elif isinstance(raw_meteo_data, RawPollutionData):
            asyncio.create_task(self._process_pollution_data(raw_meteo_data, method.delivery_tag))
        else:
            logger.warning(f"Received unknown message {body}")

    def _ack_message(self, delivery_tag: int):
        self._channel.basic_ack(delivery_tag)
        logger.debug(f"Message #{delivery_tag} acknowledged")

    def _stop_consuming(self):
        logger.info("Stopping consuming")
        if self._channel:
            self._channel.basic_cancel(self._consumer_tag, self._on_cancel_ok)

    def _on_cancel_ok(self, method_frame):
        logger.info(f"Cancel: {method_frame}")
        self._consuming = False
        self._close_channel()

    def _close_channel(self):
        logger.info("Closing channel")
        if self._channel:
            self._channel.close()

    async def _process_meteo_data(self, raw_meteo_data: RawMeteoData, delivery_tag: int):
        logger.debug(f"Processing raw meteo data {raw_meteo_data}")
        loop = asyncio.get_event_loop()
        # run blocking code in a thread pool
        wellness_data = await loop.run_in_executor(None, self._processor.process_meteo_data, raw_meteo_data)
        # wellness_data = await asyncio.to_thread(self._processor.process_meteo_data, raw_meteo_data)
        logger.debug(f"Obtained wellness data \"{wellness_data}\"")
        # convert timestamp to nanoseconds
        if await self._store.store("wellness", int(raw_meteo_data.timestamp * 1e9), wellness_data):
            logger.debug(f"Stored wellness data in redis")
        else:
            logger.warning(f"Failed to store wellness data \"{wellness_data}\"")
        self._ack_message(delivery_tag)

    async def _process_pollution_data(self, raw_pollution_data: RawPollutionData, delivery_tag: int):
        logger.debug(f"Processing raw pollution data {raw_pollution_data}")
        loop = asyncio.get_running_loop()
        # run blocking code in a thread pool
        pollution_data = await loop.run_in_executor(None, self._processor.process_pollution_data, raw_pollution_data)
        # pollution_data = await asyncio.to_thread(self._processor.process_pollution_data, raw_pollution_data)
        logger.debug(f"Obtained pollution data \"{pollution_data}\"")
        # convert timestamp to nanoseconds
        if await self._store.store("pollution", int(raw_pollution_data.timestamp * 1e9), pollution_data):
            logger.debug(f"Stored pollution data in redis")
        else:
            logger.warning(f"Failed to store pollution data \"{pollution_data}\"")
        self._ack_message(delivery_tag)
