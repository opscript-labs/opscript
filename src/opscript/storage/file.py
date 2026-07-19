from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from time import time_ns
from uuid import uuid4

from platformiq.model import DiscoveryScope, Snapshot
from platformiq.serialization import SnapshotSerializer
from platformiq.serialization.snapshot_serializer import SnapshotSerializationError

from opscript.execution import active_execution_log_fields
from opscript.logger import format_log_event, get_logger
from opscript.storage.errors import SnapshotStorageError

logger = get_logger()


class FileSnapshotStorage:
    """
    Stores snapshots on local filesystem.
    """

    def __init__(
        self,
        path: str,
        serializer: SnapshotSerializer,
        discovery_scope: DiscoveryScope,
    ):
        self.path = Path(path)
        self.serializer = serializer
        self.discovery_scope = discovery_scope

    def save(
        self,
        snapshot: Snapshot,
    ) -> None:
        started_at = perf_counter()
        self._log("snapshot_storage_save_started", operation="save")
        self._log("snapshot_storage_operation_started", operation="save")
        self._ensure_matching_scope(snapshot)

        if self.path.exists() and not self.path.is_dir():
            raise SnapshotStorageError(
                f"Append-only snapshot storage requires a directory or migration: "
                f"{self.path}"
            )

        self.path.mkdir(parents=True, exist_ok=True)

        data = self.serializer.serialize(snapshot)
        record_path = self.path / f"{time_ns()}-{uuid4().hex}.json"

        record_path.write_text(json.dumps(data))
        self._log(
            "snapshot_storage_record_write_completed",
            operation="save",
            phase="record_write",
            record_name=record_path.name,
        )
        self._latest_reference_path().write_text(record_path.name)
        self._log(
            "snapshot_storage_latest_reference_update_completed",
            operation="save",
            phase="latest_reference_update",
            record_name=record_path.name,
        )
        self._log(
            "snapshot_storage_operation_completed",
            operation="save",
            duration_ms=self._duration_ms(started_at),
        )
        self._log(
            "snapshot_storage_save_completed",
            operation="save",
            duration_ms=self._duration_ms(started_at),
            record_name=record_path.name,
        )

    def load_latest(self) -> Snapshot | None:
        started_at = perf_counter()
        self._log("snapshot_storage_load_latest_started", operation="load_latest")
        self._log("snapshot_storage_operation_started", operation="load_latest")

        if self.path.exists() and self.path.is_dir():
            latest_reference_path = self._latest_reference_path()
            if latest_reference_path.exists():
                record_name = latest_reference_path.read_text()
                record_path = self.path / record_name
                self._log(
                    "snapshot_storage_latest_reference_hit",
                    operation="load_latest",
                    phase="latest_reference",
                    record_name=record_name,
                )

                if not record_path.exists():
                    self._log(
                        "snapshot_storage_latest_reference_failed",
                        operation="load_latest",
                        phase="latest_reference",
                        reason="missing_record",
                        record_name=record_name,
                    )
                    raise SnapshotStorageError(
                        f"Latest snapshot reference points to missing record: "
                        f"{record_path}"
                    )

                try:
                    snapshot = self._load_record(record_path)
                except SnapshotStorageError:
                    self._log(
                        "snapshot_storage_latest_reference_failed",
                        operation="load_latest",
                        phase="latest_reference",
                        reason="invalid_record",
                        record_name=record_name,
                    )
                    raise

                self._log(
                    "snapshot_storage_operation_completed",
                    operation="load_latest",
                    phase="latest_reference",
                    duration_ms=self._duration_ms(started_at),
                )
                self._log(
                    "snapshot_storage_load_latest_completed",
                    operation="load_latest",
                    phase="latest_reference",
                    duration_ms=self._duration_ms(started_at),
                    fallback_used=False,
                    record_name=record_name,
                )
                return snapshot

        self._log(
            "snapshot_storage_latest_reference_missing",
            operation="load_latest",
            phase="latest_reference",
        )

        history = self.load_history()

        if not history:
            self._log(
                "snapshot_storage_operation_completed",
                operation="load_latest",
                phase="history_fallback",
                history_count=0,
                duration_ms=self._duration_ms(started_at),
            )
            self._log(
                "snapshot_storage_load_latest_completed",
                operation="load_latest",
                phase="history_fallback",
                fallback_used=True,
                history_count=0,
                duration_ms=self._duration_ms(started_at),
            )
            return None

        self._log(
            "snapshot_storage_operation_completed",
            operation="load_latest",
            phase="history_fallback",
            history_count=len(history),
            duration_ms=self._duration_ms(started_at),
        )
        self._log(
            "snapshot_storage_load_latest_completed",
            operation="load_latest",
            phase="history_fallback",
            fallback_used=True,
            history_count=len(history),
            duration_ms=self._duration_ms(started_at),
        )
        return history[-1]

    def load_history(self) -> tuple[Snapshot, ...]:
        started_at = perf_counter()
        self._log("snapshot_storage_history_load_started", operation="load_history")
        self._log("snapshot_storage_operation_started", operation="load_history")

        if not self.path.exists():
            self._log(
                "snapshot_storage_operation_completed",
                operation="load_history",
                history_count=0,
                duration_ms=self._duration_ms(started_at),
            )
            self._log(
                "snapshot_storage_history_load_completed",
                operation="load_history",
                history_count=0,
                duration_ms=self._duration_ms(started_at),
            )
            return ()

        if not self.path.is_dir():
            history = self._load_legacy_history_file()
            self._log(
                "snapshot_storage_operation_completed",
                operation="load_history",
                phase="legacy_file",
                history_count=len(history),
                duration_ms=self._duration_ms(started_at),
            )
            self._log(
                "snapshot_storage_history_load_completed",
                operation="load_history",
                phase="legacy_file",
                history_count=len(history),
                duration_ms=self._duration_ms(started_at),
            )
            return self._ensure_single_scope(history)

        history = []

        for record_path in sorted(self.path.glob("*.json")):
            history.append(self._load_record(record_path))

        loaded_history = self._ensure_single_scope(tuple(history))
        self._log(
            "snapshot_storage_operation_completed",
            operation="load_history",
            history_count=len(loaded_history),
            duration_ms=self._duration_ms(started_at),
        )
        self._log(
            "snapshot_storage_history_load_completed",
            operation="load_history",
            history_count=len(loaded_history),
            duration_ms=self._duration_ms(started_at),
        )
        return loaded_history

    def _log(
        self,
        event: str,
        **fields: object,
    ) -> None:
        logger.info(
            format_log_event(
                event,
                backend="file",
                discovery_scope=self.discovery_scope,
                path=self.path,
                **active_execution_log_fields(),
                **fields,
            )
        )

    def _duration_ms(
        self,
        started_at: float,
    ) -> int:
        return int((perf_counter() - started_at) * 1000)

    def _latest_reference_path(
        self,
    ) -> Path:
        return self.path / "latest"

    def _load_record(
        self,
        record_path: Path,
    ) -> Snapshot:
        try:
            data = json.loads(record_path.read_text())
        except json.JSONDecodeError as error:
            raise SnapshotStorageError(
                f"Malformed snapshot history file: {record_path}"
            ) from error

        return self._deserialize_record(data, str(record_path))

    def _load_legacy_history_file(self) -> tuple[Snapshot, ...]:
        try:
            data = json.loads(self.path.read_text())
        except json.JSONDecodeError as error:
            raise SnapshotStorageError(
                f"Malformed snapshot history file: {self.path}"
            ) from error

        if isinstance(data, list):
            return self._ensure_single_scope(
                tuple(self._deserialize_record(record, self.path) for record in data)
            )

        if isinstance(data, dict):
            return self._ensure_single_scope(
                (self._deserialize_record(data, self.path),)
            )

        raise SnapshotStorageError(
            f"Snapshot history file must contain an object or list: {self.path}"
        )

    def _deserialize_record(
        self,
        data: object,
        source: object,
    ) -> Snapshot:
        try:
            return self.serializer.deserialize(
                data,
                discovery_scope=self.discovery_scope,
            )
        except SnapshotSerializationError as error:
            raise SnapshotStorageError(
                f"Malformed snapshot history record: {source}"
            ) from error

    def _ensure_matching_scope(
        self,
        snapshot: Snapshot,
    ) -> Snapshot:
        if snapshot.discovery_scope != self.discovery_scope:
            raise SnapshotStorageError(
                "Snapshot discovery scope does not match storage discovery scope."
            )
        return snapshot

    def _ensure_single_scope(
        self,
        snapshots: tuple[Snapshot, ...],
    ) -> tuple[Snapshot, ...]:
        for snapshot in snapshots:
            self._ensure_matching_scope(snapshot)
        return snapshots
