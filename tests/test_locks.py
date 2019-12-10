import asyncio
import uuid

import aioredis
import pytest
import redislite

from aioredis_lock import LockTimeoutError, RedisLock


@pytest.fixture(scope="session", autouse=True)
def redis_server():
    instance = redislite.Redis(serverconfig={"port": "6380"})
    yield


@pytest.fixture
async def redis_pool(event_loop):
    pool = await aioredis.create_redis_pool("redis://127.0.0.1:6380/0")
    yield pool
    pool.close()
    await pool.wait_closed()


@pytest.fixture
async def redis_connection(event_loop):
    conn = await aioredis.create_redis("redis://127.0.0.1:6380/1")
    yield conn
    conn.close()
    await conn.wait_closed()


@pytest.fixture
async def key() -> str:
    return str(uuid.uuid4())


@pytest.mark.asyncio
async def test_acquire_lock(redis_pool, key):
    async with RedisLock(redis_pool, key) as lock:
        assert await lock.is_owner()


@pytest.fixture
def red(request):
    yield request.getfixturevalue(request.param)


@pytest.mark.asyncio
@pytest.mark.parametrize("red", ["redis_pool", "redis_connection"], indirect=["red"])
async def test_acquire_lock_timeout(red, key):
    await red.setex(key, 10, str(uuid.uuid4()))

    with pytest.raises(LockTimeoutError):
        async with RedisLock(red, key, wait_timeout=0) as lock:
            assert False, "Acquired lock when the key is set"


@pytest.mark.asyncio
@pytest.mark.parametrize("red", ["redis_pool", "redis_connection"], indirect=["red"])
async def test_extend_lock(red, key):
    async with RedisLock(red, key, timeout=10) as lock:
        await lock.extend(10)
        assert (await red.ttl(key)) > 11


@pytest.mark.asyncio
@pytest.mark.parametrize("red", ["redis_pool", "redis_connection"], indirect=["red"])
async def test_renew_lock(red, key):
    async with RedisLock(red, key, timeout=10) as lock:
        await lock.renew(10)
        assert (await red.pttl(key)) > 9 * 1000


@pytest.mark.asyncio
@pytest.mark.parametrize("red", ["redis_pool", "redis_connection"], indirect=["red"])
async def test_acquisition_failover(event_loop, red, key):
    async def task(sleep: float):
        async with RedisLock(red, key, timeout=5):
            await asyncio.sleep(sleep)
            return True

    tasks = await asyncio.gather(task(0.25), task(0))

    assert all(tasks)
