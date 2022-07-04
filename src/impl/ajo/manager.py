from datetime import timedelta
import json
from math import ceil
from os import environ
import time
import secrets

from disnake import Embed, Message
from loguru import logger
import redis

AJO = "🧄"
CRUZ = '✝️'
CHOP = "🥢"

# timely rewards, type: [reward, expire_seconds]
TIMELY = {
    "daily": [32, 86400],
    "weekly": [256, 604800]
}

LEADERBOARD = "lb"
AJOBUS = "ajobus"
AJOBUS_INVENTORY = "ajobus-inventory"
EVENT_VERSION = 1

class AjoManager:
    def __init__(self) -> None:
        self.redis = redis.Redis(host=environ['REDIS_HOST'])
        self.redis_ts = redis.Redis(host=environ['REDIS_HOST']).ts()
        logger.info("Connected to the database.")

    def __get_seed(self) -> int:
        return time.time_ns()-(int(time.time())*1000000000)

    def __translate_emoji(self, txt: str) -> str:
        match txt:
            case "🥢":
                txt = ":chopsticks:"
            case "✝️":
                txt = ":cross:"
            case "🧄":
                txt = ":garlic:"
            case "🎗️":
                txt = ":reminder_ribbon:"

        return txt

    async def __setne_name(self, user_id: str, user_name: str) -> None:
        # ensure the name we have is correct
        self.redis.evalsha(
            environ["setne"],
            1,
            user_id,
            user_name
        )

    async def contains_ajo(self, msg: Message) -> bool:
        txt = msg.content
        itxt = txt.lower()
        return "garlic" in itxt or "ajo" in itxt or AJO in txt or ":garlic" in txt

    async def is_begging_for_ajo(self, msg: Message) -> bool:
        itxt = msg.content.lower()
        return "give me garlic" in itxt or "dame ajo" in itxt

    # we only update a user's name if we give him an ajo
    async def add_ajo(self, user_id: str, user_name: str, amount: int) -> int:
        # ensure the name we have is correct
        await self.__setne_name(user_id, user_name)
        res = self.redis.zincrby(LEADERBOARD, amount, user_id)
        return int(res)

    async def get_ajo(self, user_id: str) -> int:
        res = self.redis.zscore(LEADERBOARD, user_id)
        if res is None:
            return 0
        return int(res)

    async def get_leaderboard(self) -> Embed:
        data = self.redis.zrange(LEADERBOARD, 0, 9, "rev", "withscores")
        embed = Embed(
            title="Ajo Leaderboard",
            colour=0x87CEEB,
        )

        ids = []
        scores = []
        for id, score in data:
            ids.append(id.decode("utf-8"))
            scores.append(int(score))

        names = self.redis.mget(ids)
        j = 0
        for i in range(len(names)):
            name = names[i].decode("utf-8")
            embed.add_field(
                name=f"{j} . {name[:-5]}",
                value=f"{AJO} {scores[i]}",
                inline=True,
            )
            j += 1

        return embed

    async def gamble_ajo(
        self,
        user_id: str,
        amount: str,
        guild_id: str
    ) -> str:
        if amount.isnumeric():
            amount = int(amount)
        elif amount == "all":
            amount = await self.get_ajo(user_id)
        else:
            amount = 0

        err, res = self.redis.evalsha(
            environ["gamble"],
            2,
            AJOBUS,
            LEADERBOARD,
            user_id,
            amount,
            EVENT_VERSION,
            guild_id,
            self.__get_seed()
        )

        match err.decode("utf-8"):
            case "err":
                reply = "You cannot gamble this amount."
            case "funds":
                reply = "You do not have enough ajos to gamble that much."
            case "OK":
                change = int(res)
                if change > 0:
                    reply = f"{AJO} You won {change} ajos! {AJO}"
                else:
                    reply = f"{AJO} You lost {abs(change)} ajos. {AJO}"

        return reply

    async def pay_ajo(
        self,
        from_user_id: str,
        to_user_id: str,
        amount: int,
        guild_id: str
    ) -> str:
        err, res = self.redis.evalsha(
            environ["pay"],
            2,
            AJOBUS,
            LEADERBOARD,
            from_user_id,
            to_user_id,
            amount,
            EVENT_VERSION,
            guild_id
        )

        match err.decode("utf-8"):
            case "err":
                reply = "You cannot pay this amount."
            case "futile":
                reply = "It is futile."
            case "funds":
                reply = "You do not have enough ajos to pay that much."
            case "OK":
                amount = int(res)
                reply = f"{AJO} You paid {amount} ajos to [[TO_USER]]. {AJO}"

        return reply

    async def __claim_timely(self, user_id: str, type: str, guild_id: str) -> str:
        exp_key = f"{user_id}:{type}"
        reward, expire = TIMELY[type]
        err, res = self.redis.evalsha(
            environ["timely_reward"],
            3,
            AJOBUS,
            LEADERBOARD,
            exp_key,
            user_id,
            reward,
            expire,
            EVENT_VERSION,
            guild_id
        )

        match err.decode("utf-8"):
            case "ttl":
                td = timedelta(seconds=int(res))
                reply = f"You already claimed your {type} ajos, you can claim again in {td}."
            case "OK":
                reward = int(res)
                reply = f"{AJO} You claimed your {type} ajos! {AJO}"

        return reply

    async def claim_daily(self, user_id: int, guild_id: str) -> str:
        return await self.__claim_timely(user_id, "daily", guild_id)

    async def claim_weekly(self, user_id: int, guild_id: str) -> str:
        return await self.__claim_timely(user_id, "weekly", guild_id)

    async def discombobulate(
        self,
        from_user_id: str,
        to_user_id: str,
        amount: int,
        guild_id: str
    ) -> str:
        exp_key = f"{from_user_id}:discombobulate"
        err, res = self.redis.evalsha(
            environ["discombobulate"],
            3,
            AJOBUS,
            LEADERBOARD,
            exp_key,
            from_user_id,
            to_user_id,
            amount,
            EVENT_VERSION,
            guild_id,
            self.__get_seed()
        )

        match err.decode("utf-8"):
            case "err":
                reply = "You cannot discombobulate this amount."
            case "futile":
                reply = "It is futile."
            case "ttl":
                td = timedelta(seconds=int(res))
                reply = f"You cannot discombobulate yet, next in {td}."
            case "funds":
                reply = f"You do not have enough ajos to discombobulate that much."
            case "offer":
                min_offer = int(res)
                reply = f"You have not offered enough ajos to discombobulate [[TO_USER]], needs {min_offer}."
            case "OK":
                dmg = int(res)
                reply = f"{AJO} You discombobulate [[TO_USER]] for {dmg} damage. {AJO}" \
                        "https://i.imgur.com/f2SsEqU.gif"

        return reply

    async def roulette(self) -> str:
        roulette_id = secrets.token_hex(4)
        roulette_key = f"roulette:{roulette_id}"
        err, res = self.redis.evalsha(
            environ["roulette"],
            1,
            roulette_key,
            self.__get_seed(),
            600
        )

        match err.decode("utf-8"):
            case "err":
                reply = f"Too many roulettes... {roulette_id}."
            case "OK":
                reply = f"{AJO} Roulette {roulette_id} created. {AJO}"

        return reply

    async def roulette_shot(self, user_id: str, roulette_id: str, guild_id: str) -> str:
        roulette_key = f"roulette:{roulette_id}"
        err, res = self.redis.evalsha(
            environ["roulette_shot"],
            3,
            AJOBUS,
            LEADERBOARD,
            roulette_key,
            user_id,
            EVENT_VERSION,
            guild_id
        )

        match err.decode("utf-8"):
            case "err":
                reply = "Not the roulette you are looking for."
            case "OK":
                reply = "You survived this shot."
            case "shot":
                reply = "Ded."

        return reply

    async def __build_inventory(self, items) -> Embed:
        if not items:
            items = {}

        embed = Embed(
            title="Inventory",
            colour=0x87CEEB,
        )
        for item_name, item_amount in items:
            item_amount = int(item_amount)
            if item_amount > 0:
                embed.add_field(
                    name=f"{item_name.decode()}",
                    value=f"{int(item_amount)}",
                    inline=True,
                )

        return embed

    async def get_inventory(self, user_id: str) -> Embed:
        res = self.redis.hgetall(f"{user_id}:inventory")
        return await self.__build_inventory(res.items())

    # same as get_inventory, but you pay for it
    async def see_inventory(self, from_user_id: str, to_user_id: str, guild_id: str) -> Embed | str:
        inventory_key = f"{to_user_id}:inventory"

        err, res = self.redis.evalsha(
            environ["see_inventory"],
            3,
            AJOBUS,
            LEADERBOARD,
            inventory_key,
            from_user_id,
            EVENT_VERSION,
            guild_id
        )

        match err.decode("utf-8"):
            case "funds":
                reply = f"This service is not free, {res} ajos required."
            case "OK":
                items = res[::2]
                quantities = res[1::2]
                return await self.__build_inventory(zip(items, quantities))

        return reply

    async def use(self, user_id: str, item: str, guild_id: str) -> str:
        inventory_key = f"{user_id}:inventory"
        vampire_key = f"{user_id}:vampire"

        # translate the emojis to redis compatible
        item = self.__translate_emoji(item)

        match item:
            case ":chopsticks:":
                script = "use_chopsticks"
            case ":cross:":
                script = "use_cross"
            case _:
                return f"Unknown item {item}."

        err, res = self.redis.evalsha(
            environ[script],
            3,
            AJOBUS_INVENTORY,
            inventory_key,
            vampire_key,
            user_id,
            item,
            EVENT_VERSION,
            guild_id
        )

        match err.decode("utf-8"):
            case "err":
                reply = f"You do not have enough {item}."
            case "OK":
                # FIXME: works because the only items apply to vampire for now
                reply = f"You have used {item}, vampire level decreased."

        return reply

    async def trade(
        self,
        from_user_id: str,
        to_user_id: str,
        item: str,
        qty: int,
        guild_id: str
    ) -> str:
        # translate the emojis to redis compatible
        item = self.__translate_emoji(item)
        from_inventory_key = f"{from_user_id}:inventory"
        to_inventory_key = f"{to_user_id}:inventory"

        err, res = self.redis.evalsha(
            environ["trade"],
            3,
            AJOBUS_INVENTORY,
            from_inventory_key,
            to_inventory_key,
            from_user_id,
            to_user_id,
            item,
            qty,
            EVENT_VERSION,
            guild_id
        )

        match err.decode("utf-8"):
            case "unknown":
                reply = f"No hablo {item}."
            case "err" | "funds":
                reply = f"You do not have enough {item}."
            case "futile":
                reply = "It is futile."
            case "OK":
                reply = f"You have traded {item} to [[TO_USER]]."

        return reply

    async def craft(self, user_id: str, item: str, guild_id: str) -> str:
        inventory_key = f"{user_id}:inventory"

        # translate the emojis to redis compatible
        item = self.__translate_emoji(item)

        match item:
            case ":reminder_ribbon:" | "ajo_necklace":
                item = ":reminder_ribbon:"
                script = "craft_ajo_necklace"
            case _:
                return f"Unknown item {item}."

        err, res = self.redis.evalsha(
            environ[script],
            3,
            "ajobus-inventory",
            inventory_key,
            LEADERBOARD,
            item,
            user_id,
            EVENT_VERSION,
            guild_id
        )

        match err.decode("utf-8"):
            case "err":
                reply = f"You cannot craft the {item} item."
            case "OK":
                reply = f"You have crafted {item} successfully."
            case "funds":
                reply = f"You do not have enough ajos."
            case "stack":
                reply = f"You cannot craft more {item}!"

        return reply
