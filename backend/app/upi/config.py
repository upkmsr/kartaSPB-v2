import json
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class TermsStatus(StrEnum):
    TERMS_CLEAR = "TERMS_CLEAR"
    PUBLIC_BUT_TERMS_UNCLEAR = "PUBLIC_BUT_TERMS_UNCLEAR"
    RESTRICTED = "RESTRICTED"
    UNKNOWN = "UNKNOWN"


class RawRetentionMode(StrEnum):
    FULL_RAW_ALLOWED = "FULL_RAW_ALLOWED"
    METADATA_ONLY = "METADATA_ONLY"
    SAMPLE_ONLY = "SAMPLE_ONLY"
    RETENTION_BLOCKED = "RETENTION_BLOCKED"


@dataclass(frozen=True)
class FieldContract:
    source: str
    target: str
    type: str
    required: bool


@dataclass(frozen=True)
class UpiSourceConfig:
    source_key: str
    dataset_source_name: str
    title: str
    provider: str
    source_type: str
    primary_url: str
    service_url: str
    layer_id: int
    service_type: str
    official_status: str
    provenance_kind: str
    automation_level: str
    access_mode: str
    terms_status: TermsStatus
    raw_retention_mode: RawRetentionMode
    retention_policy: dict[str, Any]
    refresh_mode: str
    enabled: bool
    license: str
    attribution: str
    adapter_key: str
    adapter_version: str
    normalization_version: str
    config_version: str
    geometry_type: str
    source_wkid: int
    source_latest_wkid: int
    output_srid: int
    object_id_field: str
    identity_field: str
    page_size: int
    timeout_seconds: int
    max_retries: int
    expected_count_min: int
    expected_count_max: int
    fields: tuple[FieldContract, ...]

    @property
    def layer_url(self) -> str:
        return f"{self.service_url.rstrip('/')}/{self.layer_id}"

    @property
    def query_url(self) -> str:
        return f"{self.layer_url}/query"

    @property
    def out_fields(self) -> tuple[str, ...]:
        return tuple(field.source for field in self.fields)


EXPECTED_KEYS = {
    "source_key",
    "dataset_source_name",
    "title",
    "provider",
    "source_type",
    "primary_url",
    "service_url",
    "layer_id",
    "service_type",
    "official_status",
    "provenance_kind",
    "automation_level",
    "access_mode",
    "terms_status",
    "raw_retention_mode",
    "retention_policy",
    "refresh_mode",
    "enabled",
    "license",
    "attribution",
    "adapter_key",
    "adapter_version",
    "normalization_version",
    "config_version",
    "geometry_type",
    "source_wkid",
    "source_latest_wkid",
    "output_srid",
    "object_id_field",
    "identity_field",
    "page_size",
    "timeout_seconds",
    "max_retries",
    "expected_count_min",
    "expected_count_max",
    "fields",
}


def project_root() -> Path:
    configured = os.getenv("PROJECT_ROOT")
    if configured:
        return Path(configured).resolve()
    return Path(__file__).resolve().parents[3]


def source_config_path(source_key: str, root: Path | None = None) -> Path:
    return (root or project_root()) / "config/upi/sources" / f"{source_key.replace('-', '_')}.json"


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"UPI source config field {key!r} must be a non-empty string")
    return value.strip()


def load_source_config(
    source_key: str = "toris-construction", root: Path | None = None
) -> UpiSourceConfig:
    path = source_config_path(source_key, root)
    with path.open(encoding="utf-8") as file:
        raw = json.load(file)
    if not isinstance(raw, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    unexpected = set(raw) - EXPECTED_KEYS
    missing = EXPECTED_KEYS - set(raw)
    if unexpected or missing:
        raise ValueError(
            f"Invalid UPI source config keys; missing={sorted(missing)}, "
            f"unexpected={sorted(unexpected)}"
        )
    if raw["source_key"] != source_key:
        raise ValueError(f"Config source_key must be {source_key!r}")
    for url_key in ("primary_url", "service_url"):
        parsed = urlparse(_required_string(raw, url_key))
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError(f"UPI source config field {url_key!r} must be an HTTPS URL")
    raw_fields = raw["fields"]
    if not isinstance(raw_fields, list) or not raw_fields:
        raise ValueError("UPI source config fields must be a non-empty list")
    fields: list[FieldContract] = []
    for item in raw_fields:
        if not isinstance(item, dict) or set(item) != {"source", "target", "type", "required"}:
            raise ValueError("Each UPI source field must define source, target, type, required")
        if not isinstance(item["required"], bool):
            raise ValueError("UPI source field required must be boolean")
        fields.append(
            FieldContract(
                source=_required_string(item, "source"),
                target=_required_string(item, "target"),
                type=_required_string(item, "type"),
                required=item["required"],
            )
        )
    sources = [field.source for field in fields]
    targets = [field.target for field in fields]
    if len(set(sources)) != len(sources) or len(set(targets)) != len(targets):
        raise ValueError("UPI source field source and target names must be unique")
    identity_field = _required_string(raw, "identity_field")
    object_id_field = _required_string(raw, "object_id_field")
    field_by_source = {field.source: field for field in fields}
    if identity_field not in field_by_source or not field_by_source[identity_field].required:
        raise ValueError("identity_field must reference a required configured field")
    if object_id_field not in field_by_source or not field_by_source[object_id_field].required:
        raise ValueError("object_id_field must reference a required configured field")
    integer_values = {
        key: raw[key]
        for key in (
            "layer_id",
            "output_srid",
            "source_wkid",
            "source_latest_wkid",
            "page_size",
            "timeout_seconds",
            "max_retries",
            "expected_count_min",
            "expected_count_max",
        )
    }
    if any(
        isinstance(value, bool) or not isinstance(value, int)
        for value in integer_values.values()
    ):
        raise ValueError("UPI numeric source settings must be integers")
    if not (1 <= raw["page_size"] <= 10_000):
        raise ValueError("page_size must be between 1 and 10000")
    if not (0 <= raw["expected_count_min"] <= raw["expected_count_max"]):
        raise ValueError("expected count range is invalid")
    if raw["output_srid"] != 4326:
        raise ValueError("UPI normalized geometry must use SRID 4326")
    retention_policy = raw["retention_policy"]
    if not isinstance(retention_policy, dict):
        raise ValueError("retention_policy must be an object")
    enabled = raw["enabled"]
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be boolean")
    return UpiSourceConfig(
        source_key=source_key,
        dataset_source_name=_required_string(raw, "dataset_source_name"),
        title=_required_string(raw, "title"),
        provider=_required_string(raw, "provider"),
        source_type=_required_string(raw, "source_type"),
        primary_url=_required_string(raw, "primary_url"),
        service_url=_required_string(raw, "service_url"),
        layer_id=raw["layer_id"],
        service_type=_required_string(raw, "service_type"),
        official_status=_required_string(raw, "official_status"),
        provenance_kind=_required_string(raw, "provenance_kind"),
        automation_level=_required_string(raw, "automation_level"),
        access_mode=_required_string(raw, "access_mode"),
        terms_status=TermsStatus(_required_string(raw, "terms_status")),
        raw_retention_mode=RawRetentionMode(_required_string(raw, "raw_retention_mode")),
        retention_policy=retention_policy,
        refresh_mode=_required_string(raw, "refresh_mode"),
        enabled=enabled,
        license=_required_string(raw, "license"),
        attribution=_required_string(raw, "attribution"),
        adapter_key=_required_string(raw, "adapter_key"),
        adapter_version=_required_string(raw, "adapter_version"),
        normalization_version=_required_string(raw, "normalization_version"),
        config_version=_required_string(raw, "config_version"),
        geometry_type=_required_string(raw, "geometry_type"),
        source_wkid=raw["source_wkid"],
        source_latest_wkid=raw["source_latest_wkid"],
        output_srid=raw["output_srid"],
        object_id_field=object_id_field,
        identity_field=identity_field,
        page_size=raw["page_size"],
        timeout_seconds=raw["timeout_seconds"],
        max_retries=raw["max_retries"],
        expected_count_min=raw["expected_count_min"],
        expected_count_max=raw["expected_count_max"],
        fields=tuple(fields),
    )
