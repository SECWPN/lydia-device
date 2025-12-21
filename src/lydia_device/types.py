from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class WsLike(Protocol):
    async def send(self, message: bytes) -> None: ...
