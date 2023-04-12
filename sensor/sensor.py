from __future__ import annotations

import json
import logging
import random
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

from pika import BlockingConnection

from common.constants import PROCESSING_QUEUE_NAME
from common.meteo_data import RawMeteoData, RawPollutionData, MeteoEncoder
from common.meteo_utils import MeteoDataDetector

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL = 1000


class SensorType(Enum):
    AirQuality = 'air_quality'
    Pollution = 'pollution'


class Sensor(ABC):
    def __init__(
            self,
            sensor_id: str,
            sensor_type: SensorType,
            detector: MeteoDataDetector,
            rabbitmq: BlockingConnection,
            interval: Optional[int] = None,
            queue_name: Optional[str] = None,
    ):
        if not sensor_id:
            raise ValueError("Sensor id must be provided")
        self._sensor_id = sensor_id
        self._sensor_type = sensor_type
        self._detector = detector
        self._interval = interval or DEFAULT_INTERVAL
        self._queue_name = queue_name or PROCESSING_QUEUE_NAME
        self._rabbitmq = rabbitmq
        self._channel = self._rabbitmq.channel()
        self._channel.queue_declare(queue=self._queue_name)

    @property
    def sensor_id(self) -> str:
        return self._sensor_id

    @property
    def sensor_type(self) -> SensorType:
        return self._sensor_type

    @abstractmethod
    def get_data(self) -> RawMeteoData | RawPollutionData:
        pass

    def send_data(self, data: RawMeteoData | RawPollutionData):
        logger.debug(f"Sending data {data} to queue {self._queue_name}")
        self._channel.basic_publish(
            exchange='',
            routing_key=self._queue_name,
            body=json.dumps(data, cls=MeteoEncoder).encode('utf-8')
        )

    def run(self):
        while True:
            time.sleep(self._interval / 1000)
            data = self.get_data()
            self.send_data(data)

    def __repr__(self):
        return f"{self._sensor_type}(id={self._sensor_id}, interval={self._interval})"


class AirQualitySensor(Sensor):
    def __init__(
            self,
            sensor_id: str,
            detector: MeteoDataDetector,
            rabbitmq: BlockingConnection,
            interval: Optional[int] = None,
            queue_name: Optional[str] = None,
    ):
        super().__init__(sensor_id, SensorType.AirQuality, detector, rabbitmq, interval, queue_name)
        logger.info(f"Initializing {self}")

    def get_data(self) -> RawMeteoData:
        air = self._detector.analyze_air()
        timestamp = time.time()
        humidity = air['humidity']
        temperature = air['temperature']
        data = RawMeteoData(temperature=temperature, humidity=humidity, timestamp=timestamp)
        logger.debug(f"{self} obtained meteo data {data}")
        return data


class PollutionSensor(Sensor):
    def __init__(
            self,
            sensor_id: str,
            detector: MeteoDataDetector,
            rabbitmq: BlockingConnection,
            interval: Optional[int] = None,
            queue_name: Optional[str] = None,
    ):
        super().__init__(sensor_id, SensorType.Pollution, detector, rabbitmq, interval, queue_name)
        logger.info(f"Initializing {self}")

    def get_data(self) -> RawPollutionData:
        pollution = self._detector.analyze_pollution()
        timestamp = time.time()
        co2 = pollution['co2']
        data = RawPollutionData(co2=co2, timestamp=timestamp)
        logger.debug(f"{self} obtained pollution data {data}")
        return data


def create_sensor(
        sensor_id: str,
        detector: MeteoDataDetector,
        rabbitmq: BlockingConnection,
        sensor_type: Optional[SensorType] = random.choice(list(SensorType)),
        interval: Optional[int] = None,
        queue_name: Optional[str] = None,
) -> Sensor:
    if sensor_type == SensorType.AirQuality:
        return AirQualitySensor(sensor_id, detector, rabbitmq, interval, queue_name)
    elif sensor_type == SensorType.Pollution:
        return PollutionSensor(sensor_id, detector, rabbitmq, interval, queue_name)
    else:
        raise ValueError(f"Invalid sensor type {sensor_type}")
