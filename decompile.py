import zlib
import struct
import click

from pathlib import Path
from PIL import Image
from jtn64 import read_palette_rgb565, print_hex, BitReader, \
    iter_colors_rgb5a3, iter_colors_rgb565, iter_colors_rgb555a, \
    iter_colors_ia8


def is_readable(t):
    readable_chars = 0

    for c in t:
        i = ord(c)

        if i > 48 and i < 122:
            readable_chars += 1

    return (readable_chars / len(t)) > 0.3


def find_strings(rom_data):
    running_string = ""

    for c in rom_data:
        i = int(c)

        if i == 32 or (i >= 48 and i <= 56) or (i >= 65 and i <= 90) or (i >= 97 and i <= 122):
            running_string += chr(c)
        else:
            if len(running_string) >= 4:
                print(running_string)

            running_string = ""


def find_models(rom_data):
    model_count = 0

    for i in range(len(rom_data) - 17):
        a = rom_data[i]
        b = rom_data[i + 1]

        if a == 0x11 and b == 0x72:
            size = int.from_bytes(rom_data[i + 2:i + 6], byteorder='big')

            if size > 5 * 1024 * 1024:
                continue

            data = rom_data[i + 6:i + size]

            try:
                decompressed = zlib.decompress(data, wbits=-15)

                if len(decompressed) > 32:
                    start, geometry_offset, texture_offset, \
                        display_list_offset, vertex_store_offset = struct.unpack(">IIIII", decompressed[0:20])

                    if start == 0x0B:
                        _, triangle_count, vertex_count, _ = struct.unpack(">HHHH", decompressed[0x30:0x38])

                        print_hex(decompressed[0:0x38])

                        print(f"Triangle_count={triangle_count}, vertex_count={vertex_count}")

                        model_path = Path(f"models/{i}_model.bin")

                        model_path.parent.mkdir(exist_ok=True)
                        model_path.write_bytes(decompressed)

                        model_count += 1
            except zlib.error as e:
                # print(e)
                pass

    print(f"Found {model_count} models.")


@click.group()
def cli():
    pass


@cli.command()
def dump_models():
    rom = Path("roms/bk_reswapped.n64")

    rom_data = rom.read_bytes()

    print(f"{len(rom_data)} bytes read.")

    find_models(rom_data)


@cli.command()
@click.argument("path")
def dump_model_textures(path: str):
    model = Path(path).read_bytes()

    texture_header_offset = struct.unpack(">H", model[8:10])[0]
    texture_header_data = model[texture_header_offset:]

    bytes_to_load = struct.unpack(">I", texture_header_data[0:4])[0]
    texture_count = texture_header_data[5]
    texture_data_start = 0x8 + (texture_count * 16)

    print(f"Bytes to load={bytes_to_load}, texture_count={texture_count}")

    for i in range(texture_count):
        print(f"Image {i}:")

        header_start = 0x8 + (i * 16)

        segment_start = struct.unpack(
            ">I", texture_header_data[header_start:header_start+4]
        )[0]
        texture_type = texture_header_data[header_start+5]
        texture_width = texture_header_data[header_start+8]
        texture_height = texture_header_data[header_start+9]

        print(
            f"segment_start={segment_start:04x},"
            f" texture_type={texture_type},"
            f" width={texture_width}, y={texture_height}"
        )

        # Types: 01=CI4, 02=CI8, 04=RGBA16, 08=RGBA32, 0x10=IA8,
        # 01/CI4: block size is 8x8

        image = Image.new('RGBA', (texture_width, texture_height))
        image_data = texture_header_data[segment_start + texture_data_start:]

        if texture_type == 1:
            # CI4

            palette = read_palette_rgb565(image_data)

            reader = BitReader(image_data[16*2:])

            for p in range(texture_height * texture_width):
                color = palette[reader.read_sub(4)]

                y = texture_height - (p // texture_width) - 1
                x = p % texture_width

                image.putpixel(
                    (x, y), color
                )

            image.save(f"image_{i}.png")
        elif texture_type == 4:
            # RGBA16, probably 555A (5 bits per color and the last bit for alpha)

            reader = BitReader(image_data)

            for p, color in enumerate(iter_colors_rgb555a(image_data, texture_height * texture_width)):
                y = texture_height - (p // texture_width) - 1
                x = p % texture_width

                image.putpixel(
                    (x, y), color
                )

            image.save(f"image_{i}.png")
        elif texture_type == 16:
            # IA8

            reader = BitReader(image_data)

            for p, color in enumerate(iter_colors_ia8(image_data, texture_height * texture_width)):
                y = texture_height - (p // texture_width) - 1
                x = p % texture_width

                image.putpixel(
                    (x, y), color
                )

            image.save(f"image_{i}.png")
        else:
            print("Unable to render texture, unknown texture type.")

        print()


if __name__ == "__main__":
    cli()

# Format:
#  n64: little-endian
#  z64: big-endian
#  u64/v64: byte-swapped
