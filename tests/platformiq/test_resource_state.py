from platformiq.model.value_objects import ResourceState


def test_resource_state_is_empty_by_default():
    state = ResourceState()

    assert state.properties == {}


def test_resource_state_stores_properties():
    state = ResourceState(
        properties={
            "instance_type": "t3.micro",
            "region": "eu-west-1",
        }
    )

    assert state.properties["instance_type"] == "t3.micro"
    assert state.properties["region"] == "eu-west-1"
