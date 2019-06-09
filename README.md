# aioredis_lock

[![CircleCI](https://circleci.com/gh/mrasband/aioredis-lock.svg?style=svg)](https://circleci.com/gh/mrasband/aioredis-lock)

Implementation of distributed locking with [aioredis](https://github.com/aio-libs/aioredis), an asyncio based redis client.

This is a standalone lib until, and if, [aio-libs/aioredis#573](https://github.com/aio-libs/aioredis/pull/573) is accepted.

## Usage

You need an `aioredis.RedisConnection` or `aioredis.ConnectionsPool` already created.

### Mutex

```python
from aioredis_lock import RedisLock, LockTimeoutError

try:
    async with RedisLock(
        pool,
        key="foobar",
        # how long until the lock should expire (seconds). this can be extended
        # via `await lock.extend(30)`
        timeout=30,
        # you can customize how long to allow the lock acquisitions to be
        # attempted.
        wait_timeout=30,
    ) as lock:
        # If you get here, you now have a lock and are the only program that
        # should be running this code at this moment.

        # do some work...

        # we may want it longer...
        await lock.extend(30)

except LockTimeoutError:
    # The lock could not be acquired by this worker and we should give up
    pass
```

### Simple Leader/Follower(s)

Let's suppose you need a simple leader/follower type implementation where you have a number of web-workers but just want 1 to preform a repeated task. In the case the leader fails someone else should pick up the work. Simply pass `wait_timeout=None` to RedisLock allowing the worker to keep trying to get a lock for when the leader eventually fails. The main complication here is extending the lock and validating the leader still owns it.

```python
from aioredis_lock import RedisLock

# if the lock is lost, we still want to be a follower
while True:

    # wait indefinitely to acquire a lock
    async with RedisLock(pool, "shared_key", wait_timeout=None) as lock:

        # hold the lock as long as possible
        while True:
            if not await lock.is_owner():
                logger.debug("We are no longer the lock owner, falling back")
                break

            # do some work

            if not await lock.renew():
                logger.debug("We lost the lock, falling back to follower mode")
                break
```

This mostly delegates the work of selecting and more importantly promoting leaders.
