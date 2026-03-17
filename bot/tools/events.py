import asyncio
from typing import Callable, Any, Optional

class EventListener:
    def __init__(self):
        self._listeners: dict[str, list[tuple[asyncio.Future, Optional[Callable]]]] = {}

    def dispatch(self, event: str, *args: Any, **kwargs: Any) -> None:
        if event not in self._listeners:
            return

        for listener in self._listeners[event].copy():
            future, check = listener

            if future.done():
                continue

            try:
                result = check(*args, **kwargs) if check else True
            except Exception as e:
                future.set_exception(e)
                continue

            if result:
                if len(args) == 0 and len(kwargs) == 0:
                    ret = None
                elif len(args) == 1 and len(kwargs) == 0:
                    ret = args[0]
                elif len(kwargs) == 0:
                    ret = args
                else:
                    ret = (args, kwargs)

                future.set_result(ret)

    async def wait_for(self, event: str, *, check: Optional[Callable[..., bool]] = None, timeout: Optional[float] = None) -> Any:
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        if event not in self._listeners:
            self._listeners[event] = []

        listener = (future, check)
        self._listeners[event].append(listener)

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            if event in self._listeners and listener in self._listeners[event]:
                self._listeners[event].remove(listener)
                if not self._listeners[event]:
                    del self._listeners[event]
