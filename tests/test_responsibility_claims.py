import pytest

from responsibilities.claims import ResponsibilityClaims


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the ResponsibilityClaims singleton between tests."""
    ResponsibilityClaims._instance = None
    yield
    ResponsibilityClaims._instance = None


async def test_try_claim_succeeds_first_time():
    claims = ResponsibilityClaims.get()
    assert await claims.try_claim("event-1") is True


async def test_try_claim_fails_on_duplicate():
    claims = ResponsibilityClaims.get()
    await claims.try_claim("event-1")
    assert await claims.try_claim("event-1") is False


async def test_release_allows_reclaim():
    claims = ResponsibilityClaims.get()
    await claims.try_claim("event-1")
    await claims.release("event-1")
    assert await claims.try_claim("event-1") is True


async def test_is_claimed_reflects_state():
    claims = ResponsibilityClaims.get()
    assert await claims.is_claimed("event-1") is False
    await claims.try_claim("event-1")
    assert await claims.is_claimed("event-1") is True


async def test_singleton_returns_same_instance():
    a = ResponsibilityClaims.get()
    b = ResponsibilityClaims.get()
    assert a is b


async def test_release_nonexistent_is_safe():
    claims = ResponsibilityClaims.get()
    await claims.release("does-not-exist")  # should not raise
