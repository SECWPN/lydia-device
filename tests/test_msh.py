import asyncio

from lydia_device.msh import MshSession


class FakeReader:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)

    async def read(self, n: int) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


class FakeWriter:
    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    async def drain(self) -> None:
        return


def test_read_until_prompt_accumulates_buffer() -> None:
    msh = MshSession("/dev/null", 115200)
    msh.reader = FakeReader([b"msh >\n"])
    msh._rx_buf = "partial\n"

    async def run() -> str:
        return await msh._read_until_prompt(timeout=0.5)

    out = asyncio.run(run())
    assert out == "partial\nmsh >\n"


def test_exec_clears_buffer_between_calls() -> None:
    msh = MshSession("/dev/null", 115200)
    msh.reader = FakeReader(
        [
            b"boot\nmsh >",
            b"msh >",
            b"out1\nmsh >",
            b"msh >",
            b"out2\nmsh >",
        ]
    )
    writer = FakeWriter()
    msh.writer = writer

    async def run() -> tuple[str, str, str]:
        first = await msh.exec("first")
        buf_after_first = msh._rx_buf
        second = await msh.exec("second")
        return first, second, buf_after_first

    out1, out2, buf_after_first = asyncio.run(run())

    assert "out1" in out1
    assert "out2" in out2
    assert "out1" not in out2
    assert buf_after_first == ""
    assert msh._rx_buf == ""
    assert writer.writes == [b"\n", b"\n", b"first\n", b"\n", b"second\n"]
