from __future__ import annotations

import asyncio
import re

import serial_asyncio

PROMPT_RE = re.compile(r"(?m)^\s*msh\s*>\s*$")
PROMPT_LINE = "msh >"


class MshSession:
    def __init__(self, serial_dev: str, baud: int):
        self.serial_dev = serial_dev
        self.baud = baud
        self.reader: asyncio.StreamReader
        self.writer: asyncio.StreamWriter
        self._rx_buf = ""
        self._lock = asyncio.Lock()
        self._bootstrapped = False

    async def connect(self) -> None:
        self.reader, self.writer = await serial_asyncio.open_serial_connection(
            url=self.serial_dev,
            baudrate=self.baud,
        )

    async def _read_until_prompt(self, timeout: float) -> str:
        end = asyncio.get_event_loop().time() + timeout
        while True:
            if PROMPT_RE.search(self._rx_buf):
                return self._rx_buf
            remaining = end - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise TimeoutError("Timed out waiting for msh prompt")
            chunk = await asyncio.wait_for(self.reader.read(512), timeout=remaining)
            if not chunk:
                await asyncio.sleep(0.01)
                continue
            self._rx_buf += chunk.decode("utf-8", errors="ignore")

    async def bootstrap(self) -> None:
        if self._bootstrapped:
            return
        self.writer.write(b"\n")
        await self.writer.drain()
        data = await self._read_until_prompt(timeout=5.0)
        self._rx_buf = data.split(PROMPT_LINE)[-1]
        self._bootstrapped = True

    async def exec(self, cmd: str, timeout: float = 5.0) -> str:
        async with self._lock:
            await self.bootstrap()

            # resync to a prompt boundary
            self.writer.write(b"\n")
            await self.writer.drain()
            await self._read_until_prompt(timeout=timeout)
            self._rx_buf = ""

            self.writer.write(cmd.strip().encode("utf-8") + b"\n")
            await self.writer.drain()

            text = await self._read_until_prompt(timeout=timeout)
            self._rx_buf = ""
            return text
            self._rx_buf = ""
            return text
