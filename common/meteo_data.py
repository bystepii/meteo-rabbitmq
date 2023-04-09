import dataclasses
from dataclasses import dataclass
from json import JSONEncoder, JSONDecoder


@dataclass
class RawMeteoData:
    temperature: float
    humidity: float
    timestamp: float


@dataclass
class RawPollutionData:
    co2: float
    timestamp: float


class MeteoEncoder(JSONEncoder):
    def default(self, o):
        data = dataclasses.asdict(o)
        data['type'] = o.__class__.__name__


class MeteoDecoder(JSONDecoder):
    def decode(self, s, _w=object()):
        data = super().decode(s)
        if data['type'] == 'RawMeteoData':
            return RawMeteoData(**data)
        if data['type'] == 'RawPollutionData':
            return RawPollutionData(**data)
        raise ValueError(f"Unknown type {data['type']}")
