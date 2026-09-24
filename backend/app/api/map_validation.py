import math
from dataclasses import dataclass

MAX_LONGITUDE_SPAN = 0.5
MAX_LATITUDE_SPAN = 0.3
MAX_BBOX_AREA = 0.1
MAX_CATEGORY_COUNT = 10


class MapRequestValidationError(ValueError):
    pass


@dataclass(frozen=True)
class BoundingBox:
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


def parse_bbox(value: str) -> BoundingBox:
    parts = value.split(",")
    if len(parts) != 4:
        raise MapRequestValidationError("bbox must contain four comma-separated coordinates")
    try:
        min_lon, min_lat, max_lon, max_lat = (float(part.strip()) for part in parts)
    except ValueError as exc:
        raise MapRequestValidationError("bbox coordinates must be numbers") from exc
    coordinates = (min_lon, min_lat, max_lon, max_lat)
    if not all(math.isfinite(coordinate) for coordinate in coordinates):
        raise MapRequestValidationError("bbox coordinates must be finite")
    if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
        raise MapRequestValidationError("bbox longitude must be between -180 and 180")
    if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise MapRequestValidationError("bbox latitude must be between -90 and 90")
    if min_lon >= max_lon or min_lat >= max_lat:
        raise MapRequestValidationError(
            "bbox must satisfy minLon < maxLon and minLat < maxLat; "
            "antimeridian crossing is unsupported"
        )
    longitude_span = max_lon - min_lon
    latitude_span = max_lat - min_lat
    if longitude_span > MAX_LONGITUDE_SPAN:
        raise MapRequestValidationError(
            f"bbox longitude span must not exceed {MAX_LONGITUDE_SPAN} degrees"
        )
    if latitude_span > MAX_LATITUDE_SPAN:
        raise MapRequestValidationError(
            f"bbox latitude span must not exceed {MAX_LATITUDE_SPAN} degrees"
        )
    if longitude_span * latitude_span > MAX_BBOX_AREA:
        raise MapRequestValidationError(
            f"bbox area must not exceed {MAX_BBOX_AREA} square degrees"
        )
    return BoundingBox(min_lon, min_lat, max_lon, max_lat)


def parse_categories(value: str) -> tuple[str, ...]:
    raw_categories = [part.strip() for part in value.split(",")]
    if any(not category for category in raw_categories):
        raise MapRequestValidationError("categories must not contain empty keys")
    if not 1 <= len(raw_categories) <= MAX_CATEGORY_COUNT:
        raise MapRequestValidationError(
            f"categories must contain between 1 and {MAX_CATEGORY_COUNT} keys"
        )
    return tuple(dict.fromkeys(raw_categories))
