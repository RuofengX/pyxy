
from typing import Any


class NetworkSafeDeco():
    def __init__(self, func):
        self.func = func
        
    def __call__(self, *args: Any, **kwds: Any) -> Any:
        try:
            rtn = self.func(*args, **kwds)
            return rtn
        except ConnectionResetError as e:
            pass
            return None
        