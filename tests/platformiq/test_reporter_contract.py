from platformiq.contracts import Reporter
from platformiq.core import Identifier
from platformiq.model import DiffResult


class FakeReporter(Reporter):
    def report(self, result: DiffResult) -> str:
        return "reported"


def test_reporter_returns_output():
    reporter = FakeReporter()

    result = reporter.report(
        DiffResult(
            previous_snapshot_id=Identifier.new(),
            current_snapshot_id=Identifier.new(),
        )
    )

    assert result == "reported"
