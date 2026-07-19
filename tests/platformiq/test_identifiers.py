from platformiq.core import Identifier


def test_identifier_new_creates_unique_identifier():
    id1 = Identifier.new()
    id2 = Identifier.new()

    assert id1 != id2
    assert str(id1)
    assert str(id2)


def test_identifier_from_string():
    original = Identifier.new()

    recreated = Identifier.from_string(str(original))

    assert recreated == original
