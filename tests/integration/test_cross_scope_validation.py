import json
from unittest.mock import patch

from platformiq.core import Identifier
from platformiq.model import DiscoveryScope, Resource, Snapshot
from platformiq.model.value_objects import ResourceState

from opscript.cli import main


class SpyStorage:
    def __init__(self, snapshots):
        self.snapshots = snapshots
        self.save_called = 0
        self.load_history_called = 0
        self.load_latest_called = 0

    def save(self, snapshot):
        self.save_called += 1

    def load_history(self):
        self.load_history_called += 1
        return self.snapshots

    def load_latest(self):
        self.load_latest_called += 1
        return self.snapshots[-1] if self.snapshots else None


def _resource(external_id: str, version: str = "1") -> Resource:
    return Resource(
        id=Identifier.new(),
        external_id=external_id,
        state=ResourceState(properties={"version": version}),
    )


def _build_test_history(
    scope: DiscoveryScope, patterns: list[list[str]]
) -> tuple[Snapshot, ...]:
    snapshots = []
    for resource_specs in patterns:
        resources = []
        for spec in resource_specs:
            parts = spec.split(":")
            ext_id = parts[0]
            ver = parts[1] if len(parts) > 1 else "1"
            resources.append(_resource(ext_id, ver))
        snapshots.append(
            Snapshot(
                discovery_scope=scope,
                id=Identifier.new(),
                resources=tuple(resources),
            )
        )
    return tuple(snapshots)


@patch("opscript.bootstrap.build_snapshot_storage")
def test_cross_scope_activity_validation_eligible_scopes(
    build_snapshot_storage, capsys
):
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")

    # scope-a: empty -> resource-1:v1 -> resource-1:v2 (1 introduced, 1 modified, 0 removed)
    # scope-b: resource-2:v1 -> empty -> resource-3:v1 (1 introduced, 0 modified, 1 removed)
    storage_a = SpyStorage(_build_test_history(scope_a, [[], ["r-1:1"], ["r-1:2"]]))
    storage_b = SpyStorage(_build_test_history(scope_b, [["r-2:1"], [], ["r-3:1"]]))

    storages = {
        "scope-a": storage_a,
        "scope-b": storage_b,
    }

    build_snapshot_storage.side_effect = lambda config=None: storages[
        config.discovery_scope.value
    ]

    exit_code = main(
        [
            "cross-scope-activity",
            "--discovery-scope",
            "scope-a",
            "--discovery-scope",
            "scope-b",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    report = captured.out

    # Human language evaluation check
    for word in [
        "best",
        "worst",
        "healthier",
        "unhealthy",
        "risky",
        "riskier",
        "unstable",
        "most active",
        "least active",
        "important",
        "efficient",
        "recommended",
        "should",
    ]:
        assert word not in report.lower(), (
            f"Forbidden evaluative word '{word}' found in report: {report}"
        )

    assert "Requested Scopes: scope-a, scope-b" in report
    assert "Eligible Scopes: scope-a, scope-b" in report
    assert "Compared Scopes: 2" in report
    assert "Scope: scope-a" in report
    assert "  Snapshot Count: 3" in report
    assert "  Valid Interval Count: 2" in report
    assert "  Endpoint Resource Count: 1" in report
    assert "  Introduced: 1" in report
    assert "  Modified: 1" in report
    assert "  Removed: 0" in report
    assert "  Total Represented Changes: 2" in report

    assert "Scope: scope-b" in report
    assert "  Snapshot Count: 3" in report
    assert "  Valid Interval Count: 2" in report
    assert "  Endpoint Resource Count: 1" in report
    assert "  Introduced: 1" in report
    assert "  Modified: 0" in report
    assert "  Removed: 1" in report
    assert "  Total Represented Changes: 2" in report

    assert "Aggregate Totals:" in report
    assert "  Total Endpoint Resources: 2" in report
    assert "  Total Introduced: 2" in report
    assert "  Total Modified: 1" in report
    assert "  Total Removed: 1" in report
    assert "  Total Represented Changes: 4" in report

    # Storage mutation check
    assert storage_a.save_called == 0
    assert storage_b.save_called == 0


@patch("opscript.bootstrap.build_snapshot_storage")
def test_cross_scope_activity_validation_three_scopes_one_excluded(
    build_snapshot_storage, capsys
):
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    scope_c = DiscoveryScope("scope-c")

    storage_a = SpyStorage(_build_test_history(scope_a, [[], ["r-1:1"]]))
    storage_b = SpyStorage(_build_test_history(scope_b, [["r-2:1"], []]))
    storage_c = SpyStorage(())  # Excluded (no history)

    storages = {
        "scope-a": storage_a,
        "scope-b": storage_b,
        scope_c.value: storage_c,
    }

    build_snapshot_storage.side_effect = lambda config=None: storages[
        config.discovery_scope.value
    ]

    exit_code = main(
        [
            "cross-scope-activity",
            "--discovery-scope",
            "scope-a",
            "--discovery-scope",
            "scope-b",
            "--discovery-scope",
            "scope-c",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    report = captured.out

    assert "Requested Scopes: scope-a, scope-b, scope-c" in report
    assert "Eligible Scopes: scope-a, scope-b" in report
    assert "Excluded Scopes:" in report
    assert "- scope-c: no_snapshot_history" in report
    assert "Compared Scopes: 2" in report


@patch("opscript.bootstrap.build_snapshot_storage")
def test_cross_scope_activity_validation_repeatability(build_snapshot_storage, capsys):
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")

    storage_a = SpyStorage(_build_test_history(scope_a, [[], ["r-1:1"]]))
    storage_b = SpyStorage(_build_test_history(scope_b, [["r-2:1"], []]))

    storages = {
        "scope-a": storage_a,
        "scope-b": storage_b,
    }

    build_snapshot_storage.side_effect = lambda config=None: storages[
        config.discovery_scope.value
    ]

    # Run 1
    main(
        [
            "cross-scope-activity",
            "--discovery-scope",
            "scope-a",
            "--discovery-scope",
            "scope-b",
        ]
    )
    report_1 = capsys.readouterr().out

    # Run 2
    main(
        [
            "cross-scope-activity",
            "--discovery-scope",
            "scope-a",
            "--discovery-scope",
            "scope-b",
        ]
    )
    report_2 = capsys.readouterr().out

    assert report_1 == report_2


@patch("opscript.bootstrap.build_snapshot_storage")
def test_cross_scope_activity_json_contract_validation(build_snapshot_storage, capsys):
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    scope_c = DiscoveryScope("scope-c")

    storage_a = SpyStorage(_build_test_history(scope_a, [[], ["r-1:1"]]))
    storage_b = SpyStorage(_build_test_history(scope_b, [["r-2:1"], []]))
    storage_c = SpyStorage(())  # Excluded

    storages = {
        "scope-a": storage_a,
        "scope-b": storage_b,
        scope_c.value: storage_c,
    }

    build_snapshot_storage.side_effect = lambda config=None: storages[
        config.discovery_scope.value
    ]

    exit_code = main(
        [
            "--json",
            "cross-scope-activity",
            "--discovery-scope",
            "scope-a",
            "--discovery-scope",
            "scope-b",
            "--discovery-scope",
            "scope-c",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert output["status"] == "success"
    assert output["workflow_status"] == "comparison_produced"
    assert output["requested_scopes"] == ["scope-a", "scope-b", "scope-c"]
    assert output["eligible_scopes"] == ["scope-a", "scope-b"]
    assert len(output["excluded_scopes"]) == 1
    assert output["excluded_scopes"][0]["discovery_scope"] == "scope-c"
    assert output["excluded_scopes"][0]["eligibility_status"] == "ineligible"
    assert output["excluded_scopes"][0]["reason"] == "no_snapshot_history"

    report = output["activity_report"]
    assert report["compared_scope_count"] == 2
    assert report["total_endpoint_resources"] == 1
    assert report["total_introduced"] == 1
    assert report["total_modified"] == 0
    assert report["total_removed"] == 1
    assert report["total_represented_changes"] == 2

    assert len(report["scope_reports"]) == 2
    scope_rep_a = report["scope_reports"][0]
    assert scope_rep_a["discovery_scope"] == "scope-a"
    assert scope_rep_a["snapshot_count"] == 2
    assert scope_rep_a["valid_interval_count"] == 1
    assert scope_rep_a["introduced_count"] == 1
    assert scope_rep_a["modified_count"] == 0
    assert scope_rep_a["removed_count"] == 0
    assert scope_rep_a["total_represented_change_count"] == 1


@patch("opscript.bootstrap.build_snapshot_storage")
def test_cross_scope_activity_global_scope_override_independence(
    build_snapshot_storage, capsys
):
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")

    storage_a = SpyStorage(_build_test_history(scope_a, [[], ["r-1:1"]]))
    storage_b = SpyStorage(_build_test_history(scope_b, [["r-2:1"], []]))

    storages = {
        "scope-a": storage_a,
        "scope-b": storage_b,
    }

    captured_configs = []

    def side_effect(config=None):
        captured_configs.append(config)
        return storages[config.discovery_scope.value]

    build_snapshot_storage.side_effect = side_effect

    # Run with global --discovery-scope set to scope-c
    exit_code = main(
        [
            "--discovery-scope",
            "scope-c",
            "cross-scope-activity",
            "--discovery-scope",
            "scope-a",
            "--discovery-scope",
            "scope-b",
        ]
    )
    assert exit_code == 0

    # Verify that the global override did not leak into storage builders for scope-a and scope-b
    assert len(captured_configs) == 2
    assert captured_configs[0].discovery_scope == DiscoveryScope("scope-a")
    assert captured_configs[1].discovery_scope == DiscoveryScope("scope-b")
