from platformiq.core import Identifier
from platformiq.model import AnalysisResult, DiffResult


def test_analysis_result_defaults_to_empty_knowledge_outputs():
    result = AnalysisResult(
        diff=DiffResult(
            previous_snapshot_id=Identifier.new(),
            current_snapshot_id=Identifier.new(),
        ),
    )

    assert result.observations == ()
    assert result.findings == ()


def test_analysis_result_is_immutable():
    result = AnalysisResult(
        diff=DiffResult(
            previous_snapshot_id=Identifier.new(),
            current_snapshot_id=Identifier.new(),
        ),
    )

    try:
        result.observations = ()
        assert False, "AnalysisResult should be immutable"
    except Exception:
        pass
