import pytest

from task_claims import TaskClaims


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the TaskClaims singleton between tests."""
    TaskClaims._instance = None
    yield
    TaskClaims._instance = None


async def test_try_claim_succeeds_first_time():
    claims = TaskClaims.get()
    assert await claims.try_claim("111") is True


async def test_try_claim_fails_on_duplicate():
    claims = TaskClaims.get()
    await claims.try_claim("111")
    assert await claims.try_claim("111") is False


async def test_release_allows_reclaim():
    claims = TaskClaims.get()
    await claims.try_claim("111")
    await claims.release("111")
    assert await claims.try_claim("111") is True


async def test_is_claimed():
    claims = TaskClaims.get()
    assert await claims.is_claimed("111") is False
    await claims.try_claim("111")
    assert await claims.is_claimed("111") is True


async def test_singleton_returns_same_instance():
    a = TaskClaims.get()
    b = TaskClaims.get()
    assert a is b


async def test_release_nonexistent_is_safe():
    claims = TaskClaims.get()
    await claims.release("does-not-exist")  # should not raise
