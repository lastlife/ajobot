--! file: timely_reward.lua
local lb_key = KEYS[1]
local timely_key = KEYS[2]

local name = ARGV[1]
local reward = math.ceil(tonumber(ARGV[2]))
local expire = tonumber(ARGV[3])

-- is this reward available?
local ttl = tonumber(redis.call("ttl", timely_key))
if ttl > 0 then
  return {"ttl", ttl}
end

redis.call("zincrby", lb_key, reward, name)
redis.call("set", timely_key, 1, "ex", expire)
return {"OK", reward}