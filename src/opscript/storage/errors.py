class SnapshotStorageError(Exception):
    """
    Raised when snapshot storage cannot safely read or write snapshot history.
    """


class SnapshotCommittedWithDegradedLatestError(SnapshotStorageError):
    """
    Raised when the append-only snapshot record is committed but latest maintenance fails.
    """

    def __init__(
        self,
        message: str,
        *,
        record_key: str,
        original_exception: Exception,
    ) -> None:
        super().__init__(message)
        self.record_key = record_key
        self.original_exception = original_exception
        self.snapshot_committed = True
        self.latest_reference_maintenance = "failed"
