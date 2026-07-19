from platformiq.core import Identifier
from platformiq.model import Resource


def test_resource_has_identifier():
    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
    )

    assert isinstance(resource.id, Identifier)


def test_resource_has_external_identifier():
    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
    )

    assert resource.external_id == "resource-001"
