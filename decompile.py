import zlib
import struct
import click

from pathlib import Path
from PIL import Image
import jtn64
from jtn64 import read_palette_rgb565, print_hex, BitReader, \
    iter_colors_rgb5a3, iter_colors_rgb565, iter_colors_rgb555a, \
    iter_colors_ia8, Model


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
    model = Model.parse_bytes(Path(path).read_bytes())

    print(f"Texture_count={model.texture_setup_header.texture_count}")

    for texture_num, texture in enumerate(model.texture_data):
        print(
            f" texture_type={texture.texture_type},"
            f" width={texture.width}, y={texture.height}"
        )

        image = Image.new('RGBA', (texture.width, texture.height))

        for p, color in enumerate(texture.to_rgba()):
            y = texture.height - (p // texture.width) - 1
            x = p % texture.width

            image.putpixel(
                (x, y), color
            )

        image.save(f"image_{texture_num}.png")


@cli.command()
@click.argument("path")
def dump_model_displaylist(path: str):
    model = Model.parse_bytes(Path(path).read_bytes())

    print(f"Command count={model.display_list_setup_header.command_count}")

    tris = 0

    for command in model.display_list_setup_header.commands:
        if command is jtn64.model.F3DCommand.G_TRI1:
            tris += 1
        elif command is jtn64.model.F3DCommand.G_TRI2:
            tris += 2
        elif command is jtn64.model.F3DCommand.G_QUAD:
            tris += 2

    print(f'tri commands={tris}')
    print(f'header tris={model.model_header.tri_count}, verts={model.model_header.vert_count}')

    for vertex in model.vertex_store_setup_header.vertices:
        print(vertex)


if __name__ == "__main__":
    cli()
