from __future__ import annotations

import json
from time import perf_counter
from time import time_ns
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from platformiq.model import DiscoveryScope, Snapshot
from platformiq.serialization import SnapshotSerializer
from platformiq.serialization.snapshot_serializer import SnapshotSerializationError

from opscript.execution import active_execution_log_fields
from opscript.logger import format_log_event, get_logger
from opscript.storage.errors import (
    SnapshotCommittedWithDegradedLatestError,
    SnapshotStorageError,
)

logger = get_logger()


class _UnusableLatestReferenceError(SnapshotStorageError):
    def __init__(
        self,
        message: str,
        *,
        latest_reference_state: str,
        record_key: str | None = None,
    ) -> None:
        super().__init__(message)
        self.latest_reference_state = latest_reference_state
        self.record_key = record_key


class S3SnapshotStorage:
    """
    Stores snapshots in Amazon S3.
    """

    def __init__(
        self,
        client,
        bucket: str,
        key: str,
        serializer: SnapshotSerializer,
        discovery_scope: DiscoveryScope,
    ):
        self.client = client
        self.bucket = bucket
        self.key = key
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

        try:
            record_keys = self._list_record_keys()
        except (ClientError, BotoCoreError) as error:
            self._log(
                "snapshot_storage_operation_failed",
                operation="save",
                phase="record_discovery",
                reason="snapshot_storage_error",
            )
            raise SnapshotStorageError(
                f"Failed to check existing S3 snapshot records in s3://{self.bucket}/{self.key}: {error}"
            ) from error

        if not record_keys:
            try:
                legacy_exists = self._legacy_object_exists()
            except (ClientError, BotoCoreError) as error:
                self._log(
                    "snapshot_storage_operation_failed",
                    operation="save",
                    phase="legacy_check",
                    reason="snapshot_storage_error",
                )
                raise SnapshotStorageError(
                    f"Failed to check legacy S3 snapshot object in s3://{self.bucket}/{self.key}: {error}"
                ) from error

            if legacy_exists:
                raise SnapshotStorageError(
                    "Append-only snapshot storage requires explicit migration: "
                    f"s3://{self.bucket}/{self.key}"
                )

        data = self.serializer.serialize(snapshot)
        record_key = f"{self._record_prefix()}{time_ns()}-{uuid4().hex}.json"

        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=record_key,
                Body=json.dumps(data),
            )
        except (ClientError, BotoCoreError) as error:
            self._log(
                "snapshot_storage_operation_failed",
                operation="save",
                phase="record_write",
                reason="snapshot_storage_error",
            )
            raise SnapshotStorageError(
                f"Failed to write snapshot record to s3://{self.bucket}/{record_key}: {error}"
            ) from error

        self._log(
            "snapshot_storage_record_write_completed",
            operation="save",
            phase="record_write",
            record_key=record_key,
        )

        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=self._latest_reference_key(),
                Body=record_key,
            )
        except (ClientError, BotoCoreError) as error:
            self._log(
                "snapshot_storage_latest_reference_maintenance_failed",
                operation="save",
                phase="latest_reference_update",
                reason="latest_reference_maintenance_failed",
                record_key=record_key,
                snapshot_committed=True,
                latest_reference_maintenance="failed",
            )
            raise SnapshotCommittedWithDegradedLatestError(
                "Snapshot record committed, but latest reference maintenance failed "
                f"for s3://{self.bucket}/{self._latest_reference_key()}: {error}",
                record_key=record_key,
                original_exception=error,
            ) from error

        self._log(
            "snapshot_storage_latest_reference_update_completed",
            operation="save",
            phase="latest_reference_update",
            record_key=record_key,
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
            record_key=record_key,
        )

    def load_latest(self) -> Snapshot | None:
        started_at = perf_counter()
        self._log("snapshot_storage_load_latest_started", operation="load_latest")
        self._log("snapshot_storage_operation_started", operation="load_latest")

        try:
            latest_record_key = self._load_latest_reference()
        except (ClientError, BotoCoreError) as error:
            self._log_read_failure(
                operation="load_latest",
                phase="latest_reference_read",
            )
            raise SnapshotStorageError(
                "Failed to load latest snapshot reference from "
                f"s3://{self.bucket}/{self._latest_reference_key()}: {error}"
            ) from error
        except _UnusableLatestReferenceError as error:
            return self._load_latest_from_history(
                started_at,
                latest_reference_state=error.latest_reference_state,
                record_key=error.record_key,
            )

        if latest_record_key is not None:
            self._log(
                "snapshot_storage_latest_reference_hit",
                operation="load_latest",
                phase="latest_reference",
                record_key=latest_record_key,
            )
            try:
                snapshot = self._load_latest_record(latest_record_key)
            except (ClientError, BotoCoreError) as error:
                self._log_read_failure(
                    operation="load_latest",
                    phase="record_read",
                    record_key=latest_record_key,
                )
                raise SnapshotStorageError(
                    "Failed to read latest snapshot record from "
                    f"s3://{self.bucket}/{latest_record_key}: {error}"
                ) from error
            except _UnusableLatestReferenceError as error:
                return self._load_latest_from_history(
                    started_at,
                    latest_reference_state=error.latest_reference_state,
                    record_key=error.record_key,
                )
            except SnapshotStorageError as error:
                if "missing record" not in str(error):
                    self._log(
                        "snapshot_storage_latest_reference_failed",
                        operation="load_latest",
                        phase="latest_reference",
                        reason="invalid_record",
                        record_key=latest_record_key,
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
                record_key=latest_record_key,
            )
            return snapshot

        self._log(
            "snapshot_storage_latest_reference_missing",
            operation="load_latest",
            phase="latest_reference",
        )

        return self._load_latest_from_history(
            started_at,
            latest_reference_state="missing",
        )

    def _load_latest_from_history(
        self,
        started_at: float,
        *,
        latest_reference_state: str,
        record_key: str | None = None,
    ) -> Snapshot | None:
        self._log(
            "snapshot_storage_latest_reference_fallback_started",
            operation="load_latest",
            phase="history_fallback",
            latest_reference_state=latest_reference_state,
            fallback_used=True,
            **({"record_key": record_key} if record_key is not None else {}),
        )

        try:
            history = self.load_history()
        except SnapshotStorageError:
            self._log(
                "snapshot_storage_latest_reference_fallback_failed",
                operation="load_latest",
                phase="history_fallback",
                latest_reference_state=latest_reference_state,
                fallback_used=True,
                **({"record_key": record_key} if record_key is not None else {}),
            )
            raise

        if not history:
            self._log(
                "snapshot_storage_operation_completed",
                operation="load_latest",
                phase="history_fallback",
                latest_reference_state=latest_reference_state,
                fallback_used=True,
                history_count=0,
                duration_ms=self._duration_ms(started_at),
            )
            self._log(
                "snapshot_storage_load_latest_completed",
                operation="load_latest",
                phase="history_fallback",
                latest_reference_state=latest_reference_state,
                fallback_used=True,
                history_count=0,
                duration_ms=self._duration_ms(started_at),
            )
            return None

        self._log(
            "snapshot_storage_operation_completed",
            operation="load_latest",
            phase="history_fallback",
            latest_reference_state=latest_reference_state,
            fallback_used=True,
            history_count=len(history),
            duration_ms=self._duration_ms(started_at),
        )
        self._log(
            "snapshot_storage_load_latest_completed",
            operation="load_latest",
            phase="history_fallback",
            latest_reference_state=latest_reference_state,
            fallback_used=True,
            history_count=len(history),
            duration_ms=self._duration_ms(started_at),
        )
        return history[-1]

    def load_history(self) -> tuple[Snapshot, ...]:
        started_at = perf_counter()
        self._log("snapshot_storage_history_load_started", operation="load_history")
        self._log("snapshot_storage_operation_started", operation="load_history")

        try:
            record_keys = self._list_record_keys()
        except (ClientError, BotoCoreError) as error:
            self._log_read_failure(
                operation="load_history",
                phase="record_discovery",
            )
            raise SnapshotStorageError(
                "Failed to list S3 snapshot records under "
                f"s3://{self.bucket}/{self._record_prefix()}: {error}"
            ) from error

        if record_keys:
            history = []
            for record_key in record_keys:
                try:
                    history.append(self._load_record(record_key))
                except (ClientError, BotoCoreError) as error:
                    self._log_read_failure(
                        operation="load_history",
                        phase="record_read",
                        record_key=record_key,
                    )
                    raise SnapshotStorageError(
                        "Failed to read S3 snapshot record from "
                        f"s3://{self.bucket}/{record_key}: {error}"
                    ) from error

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

        try:
            history = self._load_legacy_history()
        except (ClientError, BotoCoreError) as error:
            self._log_read_failure(
                operation="load_history",
                phase="legacy_read",
            )
            raise SnapshotStorageError(
                "Failed to read legacy S3 snapshot history from "
                f"s3://{self.bucket}/{self.key}: {error}"
            ) from error

        self._log(
            "snapshot_storage_operation_completed",
            operation="load_history",
            phase="legacy_object",
            history_count=len(history),
            duration_ms=self._duration_ms(started_at),
        )
        self._log(
            "snapshot_storage_history_load_completed",
            operation="load_history",
            phase="legacy_object",
            history_count=len(history),
            duration_ms=self._duration_ms(started_at),
        )
        return self._ensure_single_scope(history)

    def _log(
        self,
        event: str,
        **fields: object,
    ) -> None:
        logger.info(
            format_log_event(
                event,
                backend="s3",
                bucket=self.bucket,
                discovery_scope=self.discovery_scope,
                key=self.key,
                prefix=self._record_prefix(),
                **active_execution_log_fields(),
                **fields,
            )
        )

    def _log_read_failure(
        self,
        operation: str,
        phase: str,
        **fields: object,
    ) -> None:
        self._log(
            "snapshot_storage_operation_failed",
            operation=operation,
            phase=phase,
            reason="snapshot_storage_error",
            **fields,
        )

    def _duration_ms(
        self,
        started_at: float,
    ) -> int:
        return int((perf_counter() - started_at) * 1000)

    def _load_legacy_history(self) -> tuple[Snapshot, ...]:
        try:
            response = self.client.get_object(
                Bucket=self.bucket,
                Key=self.key,
            )
        except ClientError as error:
            if self._is_not_found(error):
                return ()
            raise

        try:
            data = json.loads(response["Body"].read())
        except json.JSONDecodeError as error:
            raise SnapshotStorageError(
                f"Malformed snapshot history object: s3://{self.bucket}/{self.key}"
            ) from error

        if isinstance(data, list):
            return self._ensure_single_scope(
                tuple(self._deserialize_record(record) for record in data)
            )

        if isinstance(data, dict):
            return self._ensure_single_scope((self._deserialize_record(data),))

        raise SnapshotStorageError(
            f"Snapshot history object must contain an object or list: "
            f"s3://{self.bucket}/{self.key}"
        )

    def _deserialize_record(
        self,
        data: object,
        source: str | None = None,
    ) -> Snapshot:
        source = source or f"s3://{self.bucket}/{self.key}"
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

    def _load_record(
        self,
        record_key: str,
    ) -> Snapshot:
        response = self.client.get_object(
            Bucket=self.bucket,
            Key=record_key,
        )

        try:
            data = json.loads(response["Body"].read())
        except json.JSONDecodeError as error:
            raise SnapshotStorageError(
                f"Malformed snapshot history object: s3://{self.bucket}/{record_key}"
            ) from error

        return self._deserialize_record(data, f"s3://{self.bucket}/{record_key}")

    def _load_latest_reference(
        self,
    ) -> str | None:
        try:
            response = self.client.get_object(
                Bucket=self.bucket,
                Key=self._latest_reference_key(),
            )
        except ClientError as error:
            if self._is_not_found(error):
                return None
            raise

        record_key = response["Body"].read()
        if isinstance(record_key, bytes):
            try:
                record_key = record_key.decode()
            except UnicodeDecodeError as error:
                raise _UnusableLatestReferenceError(
                    "Latest snapshot reference is not valid text.",
                    latest_reference_state="invalid",
                ) from error

        if not isinstance(record_key, str):
            raise _UnusableLatestReferenceError(
                "Latest snapshot reference must contain a record key.",
                latest_reference_state="invalid",
            )

        if not self._is_direct_record_key(record_key):
            latest_reference_state = "empty" if record_key == "" else "invalid"
            raise _UnusableLatestReferenceError(
                "Latest snapshot reference points outside direct namespace: "
                f"s3://{self.bucket}/{record_key}",
                latest_reference_state=latest_reference_state,
                record_key=record_key,
            )

        return record_key

    def _load_latest_record(
        self,
        record_key: str,
    ) -> Snapshot:
        try:
            return self._load_record(record_key)
        except ClientError as error:
            if self._is_not_found(error):
                self._log(
                    "snapshot_storage_latest_reference_failed",
                    operation="load_latest",
                    phase="latest_reference",
                    reason="missing_record",
                    record_key=record_key,
                )
                raise _UnusableLatestReferenceError(
                    "Latest snapshot reference points to missing record: "
                    f"s3://{self.bucket}/{record_key}",
                    latest_reference_state="missing_target",
                    record_key=record_key,
                ) from error
            raise

    def _list_record_keys(self) -> list[str]:
        return sorted(
            item["Key"]
            for response in self._list_record_pages()
            for item in response.get("Contents", [])
            if self._is_direct_record_key(item["Key"])
        )

    def _list_record_pages(self):
        if hasattr(self.client, "get_paginator"):
            paginator = self.client.get_paginator("list_objects_v2")
            return paginator.paginate(
                Bucket=self.bucket,
                Prefix=self._record_prefix(),
            )

        return (
            self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=self._record_prefix(),
            ),
        )

    def _legacy_object_exists(self) -> bool:
        try:
            self.client.get_object(
                Bucket=self.bucket,
                Key=self.key,
            )
        except ClientError as error:
            if self._is_not_found(error):
                return False
            raise

        return True

    def _record_prefix(self) -> str:
        return f"{self.key.rstrip('/')}/"

    def _latest_reference_key(self) -> str:
        return f"{self._record_prefix()}latest"

    def _is_direct_record_key(
        self,
        key: str,
    ) -> bool:
        return key.endswith(".json") and self._is_direct_child_key(key)

    def _is_direct_child_key(
        self,
        key: str,
    ) -> bool:
        prefix = self._record_prefix()
        if not key.startswith(prefix):
            return False

        remainder = key[len(prefix) :]
        return bool(remainder) and "/" not in remainder

    def _is_not_found(
        self,
        error: ClientError,
    ) -> bool:
        error_code = error.response.get("Error", {}).get("Code", "")
        return error_code in {"NoSuchKey", "404", "NotFound"}
