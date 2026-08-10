from discord.ext import tasks

TASK_REGISTRY: list[tasks.Loop] = []

def register_task(*args, **kwargs):
    def decorator(func):
        loop_obj = tasks.loop(*args, **kwargs)(func)
        TASK_REGISTRY.append(loop_obj)
        return loop_obj
    return decorator
