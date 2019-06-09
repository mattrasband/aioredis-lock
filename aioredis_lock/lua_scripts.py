# Script to acquire the lock and ensure it will expire
# param: keys[1] - key to lock on (shared)
# param: argv[1] - this lock's token (unique)
# param: argv[2] - expiration in milliseconds
ACQUIRE_SCRIPT = """
if redis.call('setnx', KEYS[1], ARGV[1]) == 1 then
    redis.call('pexpire', KEYS[1], ARGV[2])
    return 1
else
    return 0
end
"""

# Script to release the lock, this will only delete the lock token
# if it's the lock obtained from the provided lock token (args[1])
# param: keys[1] - key to lock on (shared)
# param: args[1] - this lock's token (unique)
# returns: 1 if released, otherwise 0
RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""

# Extend the lock, this will only extend if the current lock holder
# is the provided token (args[1])
# param: keys[1] - key to lock on (shared)
# param: args[1] - this lock's token (unique)
# param: args[2] - additional millis to keep the lock
# returns: 1 if extended, otherwise 0
EXTEND_SCRIPT = """
if redis.call('get', KEYS[1]) ~= ARGV[1] then
    return 0
end
local expiration = redis.call('pttl', KEYS[1])
if expiration < 0 then
    return 0
end
redis.call('pexpire', KEYS[1], expiration + ARGV[2])
return 1
"""

# Renew the lock setting a new expiration time, instead of an incremental extension,
# if the current token (ARGV[1]) holds the lock. This is useful to do a quick renew
# instead of doing an incremental extension, which could cause the expiration to be
# indefinite.
# param: keys[1] - key to lock on (shared)
# param: argv[1] - lock token (unique)
# param: argv[2] - expiration in millis
RENEW_SCRIPT = """
if redis.call('get', KEYS[1]) ~= ARGV[1] or redis.call('pttl', KEYS[1]) < 0 then
    return 0
end
redis.call('pexpire', KEYS[1], ARGV[2])
return 1
"""
