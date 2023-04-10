import json
import logging
from collections import deque
from datetime import datetime
from json import JSONDecodeError
from threading import Thread
from typing import Deque, Tuple, Optional

import matplotlib.pyplot as plt
from pika import BlockingConnection, URLParameters
from pika.channel import Channel
from pika.spec import Basic, BasicProperties

from common.constants import RESULT_EXCHANGE_NAME
from common.meteo_data import Results, MeteoDecoder

logger = logging.getLogger(__name__)


class Terminal:
    def __init__(
            self,
            rabbitmq_address: str,
            max_results: int = 50,
            exchange_name: Optional[str] = None,
    ):
        logger.info("Initializing Terminal")
        self._exchange_name = exchange_name or RESULT_EXCHANGE_NAME
        self._rabbitmq = BlockingConnection(URLParameters(rabbitmq_address))
        self._channel = self._rabbitmq.channel()
        self._channel.exchange_declare(exchange=self._exchange_name, exchange_type='fanout')
        self._queue_name = self._channel.queue_declare(queue='', exclusive=True).method.queue
        self._channel.queue_bind(exchange=self._exchange_name, queue=self._queue_name)
        self._max_results = max_results
        self._wellness_data: Deque[Tuple[str, float]] = deque(maxlen=max_results)
        self._pollution_data: Deque[Tuple[str, float]] = deque(maxlen=max_results)
        self._animation = None
        self._plot_process = None
        self._fig, (self._ax1, self._ax2) = plt.subplots(2)

    def receive_results(self, results: Results):
        logger.debug(f"Received results: {results}")
        if results.wellness_timestamp != 0:
            self._wellness_data.append((
                datetime.fromtimestamp(results.wellness_timestamp).strftime('%H:%M:%S.%f'),
                results.wellness_data
            ))
        if results.pollution_timestamp != 0:
            self._pollution_data.append((
                datetime.fromtimestamp(results.pollution_timestamp).strftime('%H:%M:%S.%f'),
                results.pollution_data
            ))

        if len(self._wellness_data) > self._max_results:
            self._wellness_data.popleft()
        if len(self._pollution_data) > self._max_results:
            self._pollution_data.popleft()

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
            return
        if isinstance(raw_meteo_data, Results):
            self.receive_results(raw_meteo_data)
            self._update_plot()
        else:
            logger.warning(f"Received unknown message {body}")

    def _update_plot(self):
        # clear the plot
        self._ax1.clear()
        self._ax2.clear()

        # wellness data
        self._ax1.set_title("Wellness data")
        self._ax1.set_xlabel("Timestamp")
        self._ax1.set_ylabel("Wellness")

        w = self._wellness_data
        logger.debug(f"Plotting wellness data: {w}")
        self._ax1.plot([x[0] for x in w], [x[1] for x in w])

        # pollution data
        self._ax2.set_title("Pollution data")
        self._ax2.set_xlabel("Timestamp")
        self._ax2.set_ylabel("Pollution")

        p = self._pollution_data
        logger.debug(f"Plotting pollution data: {p}")
        self._ax2.plot([x[0] for x in p], [x[1] for x in p])

        # format the plot
        self._ax1.set_xticklabels(self._ax1.get_xticklabels(), rotation=45, ha='right')
        self._ax2.set_xticklabels(self._ax2.get_xticklabels(), rotation=45, ha='right')
        plt.subplots_adjust(bottom=0.30)
        plt.tight_layout()

        self._fig.canvas.draw()

    def run(self):
        logger.info("Running Terminal")

        self._channel.basic_consume(
            queue=self._queue_name,
            on_message_callback=self._on_message,
            auto_ack=True
        )

        logger.debug("Plotting data")

        logger.debug("Starting to consume results")
        t = Thread(target=self._channel.start_consuming)
        t.start()

        plt.show()

        t.join()
