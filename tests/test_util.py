import struct
from jtn64 import BitReader


def test_bitreader():
    data = struct.pack("BB", 0b10100010, 0b11000000)

    reader = BitReader(data)

    assert reader.read_sub(1) == 1
    assert reader.read_sub(1) == 0
    assert reader.read_sub(1) == 1
    assert reader.read_sub(5) == 2
    assert reader.read_sub(2) == 3
