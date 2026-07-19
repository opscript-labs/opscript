import pytest

from platformiq.errors import ProviderError


def test_provider_error_is_exception():
    error = ProviderError("provider failure")

    assert isinstance(error, Exception)
    assert str(error) == "provider failure"


def test_provider_error_can_be_raised():
    with pytest.raises(ProviderError):
        raise ProviderError("provider failure")
