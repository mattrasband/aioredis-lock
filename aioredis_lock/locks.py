import asyncio

import dataclasses
import time
import uuid
from typing import List, Optional

from aioredis import ConnectionsPool

from .errors import LockTimeoutError
from .lua_scripts import ACQUIRE_SCRIPT, EXTEND_SCRIPT, RELEASE_SCRIPT, RENEW_SCRIPT


def token_factory() -> str:
    """
    Generate a sufficiently random/unique token.
    """
    return str(uuid.uuid4())


@dataclasses.dataclass
class RedisLock:
    """
    Implementation of distributed locking with aioredis.
    """

    # The aioredis pool or connection object
    pool_or_conn: ConnectionsPool

    # The key to lock on in redis
    key: str

    # How long until the lock should automatically be timed out in seconds.
    # This is useful to ensure the lock is released in the event of an app crash
    timeout: int = 30

    # How long to wait before aborting attempting to acquire a lock. This
    # can be set to None to allow for an infinite timeout. This is useful
    # for cases in which you want only one worker active.
    wait_timeout: int = 30

    # Used internally for uniquely identifying this lock instance.
    _token: str = dataclasses.field(default_factory=token_factory, init=False)

    # Used internally for storing the SHA of loaded lua scripts
    _acquire_script: Optional[str] = dataclasses.field(default=None, init=False)
    _extend_script: Optional[str] = dataclasses.field(default=None, init=False)
    _release_script: Optional[str] = dataclasses.field(default=None, init=False)
    _renew_script: Optional[str] = dataclasses.field(default=None, init=False)

    async def acquire_script(self) -> str:
        if self._acquire_script is None:
            self._acquire_script = await self.pool_or_conn.script_load(ACQUIRE_SCRIPT)
        return self._acquire_script

    async def extend_script(self) -> str:
        if self._extend_script is None:
            self._extend_script = await self.pool_or_conn.script_load(EXTEND_SCRIPT)
        return self._extend_script

    async def release_script(self) -> str:
        if self._release_script is None:
            self._release_script = await self.pool_or_conn.script_load(RELEASE_SCRIPT)
        return self._release_script

    async def renew_script(self) -> str:
        if self._renew_script is None:
            self._renew_script = await self.pool_or_conn.script_load(RENEW_SCRIPT)
        return self._renew_script

    async def __aenter__(self):
        if await self.acquire(self.key, self.timeout, self.wait_timeout):
            return self

        raise LockTimeoutError("Unable to acquire lock within timeout")

    async def __aexit__(self, *args, **kwargs):
        await self.release()

    async def is_owner(self) -> bool:
        """Determine if the instance is the owner of the lock"""
        return (
            await self.pool_or_conn.get(self.key)
        ) == self._token.encode()  # pylint: disable=no-member

    async def acquire(self, key, timeout=30, wait_timeout=30) -> bool:
        """
        Attempt to acquire the lock

        :param key: Lock key
        :param timeout: Number of seconds until the lock should timeout. It can
                        be extended via extend
        :param wait_timeout: How long to wait before aborting the lock request
        :returns: bool, true if acquired false otherwise.
        """
        start = int(time.time())
        while True:
            if await self._script_exec(
                (await self.acquire_script()),
                keys=[key],
                args=[self._token, timeout * 1000],
            ):
                return True

            if wait_timeout is not None and int(time.time()) - start > wait_timeout:
                return False

            await asyncio.sleep(0.1)

    async def extend(self, added_time: int) -> bool:
        """
        Attempt to extend the lock by the amount of time, this will only extend
        if this instance owns the lock. Note that this is _incremental_, meaning
        that adding time will be on-top of however much time is already available.

        :param added_time: Number of seconds to add to the lock expiration
        :returns: bool of the success
        """
        return await self._script_exec(
            (await self.extend_script()),
            keys=[self.key],
            args=[self._token, added_time * 1000],
        )

    async def release(self) -> bool:
        """
        Release the lock, this will only release if this instance of the lock
        is the one holding the lock.
        :returns: bool of the success
        """
        return await self._script_exec(
            (await self.release_script()), keys=[self.key], args=[self._token]
        )

    async def renew(self, timeout: Optional[int] = 30) -> bool:
        """
        Renew the lock, setting expiration to now + timeout (or self.timeout if not provided).
        This will only
        succeed if the instance is the lock owner.

        :returns: 1 if the release was successful, 0 otherwise.
        """
        return await self._script_exec(
            (await self.renew_script()),
            keys=[self.key],
            args=[self._token, (timeout or self.timeout) * 1000],
        )

    async def _script_exec(self, sha: str, keys: List[str], args: List[str]) -> bool:
        """
        Execute the script with the provided keys and args.
        :param sha: Script sha, returned after the script was loaded
        :param keys: Keys to the script
        :param args: Args to the script
        :returns: bool
        """
        return bool(await self.pool_or_conn.evalsha(sha, keys=keys, args=args))
