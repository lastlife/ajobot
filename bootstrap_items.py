# this file is used to generate redis protocol in order to bulk load the
# item data (max stack, currency, prices, chance to appear)
def proto(cmd, key, data) -> None:
    # stringify the data
    strings = [cmd, key]
    for value in data:
        strings.append(value)

    # transform to redis proto
    arg_count = len(strings)
    parts = [f"*{arg_count}"]
    for s in strings:
        parts.extend([f"${len(s)}", s])

    # clear up the key
    sz = len(key)
    print(f"*2\r\n$3\r\nDEL\r\n${sz}\r\n{key}", end="\r\n")
    print("\r\n".join(parts), end="\r\n")

def main() -> None:
    data = {
        ":sauropod:": {
            "drop_rate": 1,
            "max_stack": 1
        },
        ":chopsticks:": {
            "drop_rate": 6,
            "max_stack": 5
        },
        ":cross:": {
            "drop_rate": 500,
            "max_stack": 10,
            "craft": {
                ":garlic:": 50
            }
        },
        ":bomb:": {
            "drop_rate": 200,
            "max_stack": 1
        },
        ":herb:": {
            "drop_rate": 1000,
            "max_stack": 20
        },
        ":reminder_ribbon:": {
            "max_stack": 1,
            "craft": {
                ":herb:": 4
            }
        }
    }

    protos = []
    drop_rate = []
    for item, item_data in data.items():
        # prepare drop rate hash
        if "drop_rate" in item_data:
            drop_rate.extend([item, str(item_data["drop_rate"]), str(item_data["max_stack"])])

        # prototype the item hash, note that we use a list for simplicity
        hitem = []
        for key, value in item_data.items():
            if key != "craft":
                hitem.extend([key, str(value)])
        proto("HSET", "items:{}".format(item), hitem)

        # prototype the craft data
        if "craft" in item_data:
            craft_data = []
            for key, value in item_data["craft"].items():
                craft_data.extend([key, str(value)])
            proto("RPUSH", "craft:{}".format(item), craft_data)

    # prototype drop rate, but clear it first
    proto("RPUSH", "drop-rate", drop_rate)

main()