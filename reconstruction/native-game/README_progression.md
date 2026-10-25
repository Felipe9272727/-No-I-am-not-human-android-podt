# Day/night progression adapter

The module holds the recovered state changes and delegates Unity services through required host callbacks. Production DayConfig is supplied by extracted game data; no threshold defaults are embedded. Successful transition clock values use `current_time + accumulated_time`, matching the recovered LastChange normalization. The DayActions refill runs after morning, pose, and character-count callbacks so their mutations to current fines and extra slots are reflected.

Some event subscribers and visual effects remain host-provided. This module does not reproduce visual coroutine timing or Unity object behavior.
