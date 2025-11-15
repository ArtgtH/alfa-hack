from dataclasses import dataclass


@dataclass
class Chunk:
    chunk_content: str
    chunk_serial: int


async def vectorize(content: str):
    return [Chunk(chunk_content="test", chunk_serial=serial) for serial in range(0, 10)]
