from .util import BitReader
from enum import IntEnum


class TextureType(IntEnum):
    CI4 = 1
    CI8 = 2
    RGBA16 = 4
    RGBA32 = 8
    IA8 = 16


def iter_colors_rgb5a3(data, size):
    palette_reader = BitReader(data)

    for _ in range(size):
        if palette_reader.read_sub(1) == 0:
            alpha = palette_reader.read_sub(3) * 0x20
            red = palette_reader.read_sub(4) * 0x11
            green = palette_reader.read_sub(4) * 0x11
            blue = palette_reader.read_sub(4) * 0x11
        else:
            alpha = 255

            red = palette_reader.read_sub(5) * 0x8
            green1 = palette_reader.read_sub(2)
            green2 = palette_reader.read_sub(3)
            blue = palette_reader.read_sub(5) * 0x8

            green = ((green1 << 3) & green2) * 0x8

        yield red, green, blue, alpha


def iter_colors_rgb565(data, size):
    # Used for texture type 1 (CI4)

    reader = BitReader(data)

    for _ in range(size):
        red = reader.read_sub(5) * 0x8
        green1 = reader.read_sub(3)
        green2 = reader.read_sub(3)
        blue = reader.read_sub(5) * 0x8

        green = ((green1 << 3) | green2) * 0x4

        yield red, green, blue, 255


def iter_colors_rgb555a(data, size):
    reader = BitReader(data)

    for _ in range(size):
        red = reader.read_sub(5) * 0x8
        green1 = reader.read_sub(3)
        green2 = reader.read_sub(2)
        blue = reader.read_sub(5) * 0x8
        alpha = reader.read_sub(1) * 0xFF

        green = ((green1 << 2) | green2) * 0x8

        yield red, green, blue, alpha


def iter_colors_ia8(data, size):
    reader = BitReader(data)

    for _ in range(size):
        color = reader.read_sub(8)

        yield (color, color, color, color)


def read_palette_rgb5a3(data):
    palette = []

    for color in iter_colors_rgb5a3(data, 16):
        palette.append(color)

    return palette


def read_palette_rgb565(data):
    palette = []

    for color in iter_colors_rgb565(data, 16):
        palette.append(color)

    return palette


def read_palette_rgb555a(data):
    palette = []

    for color in iter_colors_rgb555a(data, 16):
        palette.append(color)

    return palette
