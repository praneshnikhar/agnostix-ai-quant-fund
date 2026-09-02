"""Hash-chained audit journal.

Every entry carries a SHA-256 hash that commits to the PREVIOUS entry's
hash plus its own content. Tampering with any historical entry breaks the
chain — a judge can verify the whole ledger with one credential-free
command. The chain is monotonic and append-only by construction.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

GENESIS_HASH = "0" * 64


class JournalEntry(BaseModel):
    seq: int
    timestamp: datetime
    kind: str
    symbol: str
    payload: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str
    hash: str


def _hash(prev_hash: str, entry: dict[str, Any]) -> str:
    canonical = json.dumps(entry, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256((prev_hash + canonical).encode("utf-8")).hexdigest()


class TradingJournal:
    """Append-only hash chain for every decision, order, and refusal."""

    def __init__(self, entries: list[JournalEntry] | None = None) -> None:
        self._entries: list[JournalEntry] = list(entries or [])
        self._prev_hash = self._entries[-1].hash if self._entries else GENESIS_HASH

    @property
    def entries(self) -> list[JournalEntry]:
        return list(self._entries)

    @property
    def head_hash(self) -> str:
        return self._prev_hash

    def append(self, kind: str, symbol: str, payload: dict[str, Any]) -> JournalEntry:
        seq = len(self._entries)
        timestamp = datetime.now(UTC)
        body = {
            "seq": seq,
            "kind": kind,
            "symbol": symbol,
            "payload": payload,
            "ts": timestamp.isoformat(),
        }
        digest = _hash(self._prev_hash, body)
        entry = JournalEntry(
            seq=seq,
            timestamp=timestamp,
            kind=kind,
            symbol=symbol,
            payload=payload,
            prev_hash=self._prev_hash,
            hash=digest,
        )
        self._entries.append(entry)
        self._prev_hash = digest
        return entry

    def verify(self) -> bool:
        """Recompute the chain from genesis; True only if nothing was altered."""
        prev = GENESIS_HASH
        for entry in self._entries:
            body = {
                "seq": entry.seq,
                "kind": entry.kind,
                "symbol": entry.symbol,
                "payload": entry.payload,
                "ts": entry.timestamp.isoformat(),
            }
            if entry.prev_hash != prev:
                return False
            if _hash(prev, body) != entry.hash:
                return False
            prev = entry.hash
        return True
