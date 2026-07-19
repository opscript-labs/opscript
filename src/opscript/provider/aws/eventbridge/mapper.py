from __future__ import annotations

from platformiq.core import Identifier
from platformiq.model import Resource
from platformiq.model.value_objects import ResourceState


class EventBridgeResourceMapper:
    """
    Converts AWS EventBridge rule representations into PlatformIQ resources.
    """

    def map(
        self,
        rule: dict,
    ) -> Resource:
        return Resource(
            id=Identifier.new(),
            external_id=rule["Name"],
            state=ResourceState(
                properties={
                    "arn": rule.get("Arn"),
                    "event_bus_name": rule.get("EventBusName"),
                    "state": rule.get("State"),
                    "schedule_expression": rule.get("ScheduleExpression"),
                    "event_pattern": rule.get("EventPattern"),
                    "description": rule.get("Description"),
                }
            ),
        )
