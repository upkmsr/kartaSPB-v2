from datetime import datetime
from typing import Protocol

from app.upi.arcgis import ArcGisClient, ArcGisEvidence, ArcGisProbe
from app.upi.config import UpiSourceConfig
from app.upi.normalization import NormalizedSnapshot, normalize_features


class SourceAdapter(Protocol):
    """Small source boundary; transport details stay outside persistence orchestration."""

    config: UpiSourceConfig

    def probe(self) -> ArcGisProbe: ...

    def fetch_snapshot(self) -> ArcGisEvidence: ...

    def normalize(
        self, evidence: ArcGisEvidence, *, observed_at: datetime
    ) -> NormalizedSnapshot: ...


class TorisConstructionAdapter:
    def __init__(self, config: UpiSourceConfig, client: ArcGisClient | None = None) -> None:
        self.config = config
        self.client = client or ArcGisClient(config)

    def probe(self) -> ArcGisProbe:
        return self.client.probe()

    def fetch_snapshot(self) -> ArcGisEvidence:
        return self.client.fetch_all()

    def normalize(
        self, evidence: ArcGisEvidence, *, observed_at: datetime
    ) -> NormalizedSnapshot:
        return normalize_features(
            evidence.features,
            evidence.metadata,
            self.config,
            observed_at=observed_at,
        )
