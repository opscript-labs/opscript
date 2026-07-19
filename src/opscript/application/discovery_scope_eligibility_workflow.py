from platformiq.model import DiscoveryScope

from opscript.application.discovery_scope_eligibility_service import (
    DiscoveryScopeEligibilityService,
)
from opscript.models import DiscoveryScopeEligibility


class DiscoveryScopeEligibilityWorkflow:
    """
    Workflow boundary for qualifying one selected Discovery Scope.
    """

    def __init__(
        self,
        eligibility_service: DiscoveryScopeEligibilityService,
    ):
        self.eligibility_service = eligibility_service

    def run(
        self,
        discovery_scope: DiscoveryScope,
        storage,
    ) -> DiscoveryScopeEligibility:
        return self.eligibility_service.qualify(
            discovery_scope,
            storage,
        )
