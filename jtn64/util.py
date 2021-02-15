def print_hex(*data):
    output = []

    for d in data:
        r = [f"{x:02x}" for x in d]

        output.append(" ".join(r))

    print(" ".join(output))


def reswap_bytes(i):
    return bytes([i[1], i[0], i[3], i[2]])


class BitReader:
    def __init__(self, data: bytes):
        self._data = data
        self._bit_offset = 0
        self._byte_offset = 0
        self._bits_remaining = 8

        self._current_byte = self._data[self._byte_offset]

    def read_sub(self, bits):
        """
        A very limited version of read_bits that must be along byte boundaries.
        """

        result = self._current_byte

        result >>= (8 - bits)

        self._current_byte = (self._current_byte << bits) & 0xFF
        self._bits_remaining -= bits

        if self._bits_remaining == 0:
            self._bits_remaining = 8
            self._byte_offset += 1

            if self._byte_offset < len(self._data):
                self._current_byte = self._data[self._byte_offset]
            else:
                self._current_byte = None
        elif self._bits_remaining < 0:
            raise ValueError("Failed to read along byte boundary.")

        return result

    def read_bits(self, bits):
        raise NotImplementedError
