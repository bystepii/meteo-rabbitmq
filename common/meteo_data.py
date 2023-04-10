import dataclasses
from dataclasses import dataclass
from json import JSONEncoder, JSONDecoder, JSONDecodeError


@dataclass
class RawMeteoData:
    temperature: float
    humidity: float
    timestamp: float


@dataclass
class RawPollutionData:
    co2: float
    timestamp: float


@dataclass
class Results:
    wellness_data: float
    wellness_timestamp: float
    pollution_data: float
    pollution_timestamp: float


class MeteoEncoder(JSONEncoder):
    def default(self, o):
        data = dataclasses.asdict(o)
        data['type'] = o.__class__.__name__
        return data


class MeteoDecoder(JSONDecoder):
    def decode(self, s, _w=object()):
        data = super().decode(s)
        try:
            data_type = data['type']
        except (KeyError, TypeError):
            raise JSONDecodeError("Missing type field", s, 0)
        data.pop('type')
        if data_type == 'RawMeteoData':
            return RawMeteoData(**data)
        elif data_type == 'RawPollutionData':
            return RawPollutionData(**data)
        elif data_type == 'Results':
            return Results(**data)
        else:
            raise JSONDecodeError(f"Unknown type {data['type']}", s, 0)
