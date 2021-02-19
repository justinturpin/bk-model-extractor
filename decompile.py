import zlib
import struct
import click
import io

from pathlib import Path
from PIL import Image
import jtn64
from jtn64 import read_palette_rgb565, print_hex, BitReader, \
    iter_colors_rgb5a3, iter_colors_rgb565, iter_colors_rgb555a, \
    iter_colors_ia8, Model

import pygltflib
from pygltflib.validator import validate, summary


class MinMaxTracker:
    def __init__(self):
        self.min = None
        self.max = None

    def add(self, v):
        if not self.min:
            self.min = v
        elif v < self.min:
            self.min = v

        if not self.max:
            self.max = v
        elif v > self.max:
            self.max = v


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
            f" texture_type={texture.texture_type!s},"
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
    path = Path(path)
    model = Model.parse_bytes(path.read_bytes())

    print("--------------------------")
    print("Model loaded")

    print(f"Command count={model.display_list_setup_header.command_count}")

    tris = 0

    for command in model.display_list_setup_header.commands:
        print(command)

        if command is jtn64.F3DCommandType.G_TRI1:
            tris += 1
        elif command is jtn64.F3DCommandType.G_TRI2:
            tris += 2
        elif command is jtn64.F3DCommandType.G_QUAD:
            tris += 2

    print(f'tri commands={tris}')
    print(f'header tris={model.model_header.tri_count}, verts={model.model_header.vert_count}')
    print(f'texture count={model.texture_setup_header.texture_count}')

    # print(f'vertex store segment={model.model_header.vertex_store_setup_offset}')

    # for vertex in model.vertex_store_setup_header.vertices:
    #     print(vertex)

    images = []
    textures = []
    materials = []
    vertex_io = io.BytesIO()
    triangle_io = io.BytesIO()

    vertex_count = 0
    triangle_count = 0

    triangle_minmax = MinMaxTracker()
    vertex_minmax = MinMaxTracker()
    color_minmax = MinMaxTracker()
    uv_minmax = MinMaxTracker()

    for vertex in model.vertex_store_setup_header.vertices:
        position = (
            vertex.position[0] / 10,
            vertex.position[1] / 10,
            vertex.position[2] / 10
        )

        color = (
            vertex.rgb_or_norm[0],
            vertex.rgb_or_norm[1],
            vertex.rgb_or_norm[2],
        )

        uv = (
            float(vertex.uv[0]),
            float(vertex.uv[1]),
        )

        vertex_io.write(struct.pack("fff", *position))
        vertex_io.write(struct.pack("BBBB", 0, *color))
        vertex_io.write(struct.pack("ff", *uv))

        vertex_minmax.add(position)
        color_minmax.add(color)
        uv_minmax.add(uv)

        vertex_count += 1

    for face in model.simulate_displaylist():
        triangle_io.write(struct.pack("HHH", *face))

        triangle_minmax.add(face[0])
        triangle_minmax.add(face[1])
        triangle_minmax.add(face[2])

        triangle_count += 3

    for i, texture in enumerate(model.texture_data):
        print(f"Texture {i}: {texture.width}x{texture.height}")

        image = texture.to_image()

        images.append(
            pygltflib.Image(uri=jtn64.image_to_data_uri(image))
        )

        textures.append(
            pygltflib.Texture(sampler=0, source=i)
        )

        materials.append(
            pygltflib.Material(
                pbrMetallicRoughness=pygltflib.PbrMetallicRoughness(
                    baseColorTexture=pygltflib.TextureInfo(
                        index=0
                    ),
                    metallicFactor=0.0
                ),
                name=f"texture_{i}"
            )
        )

    gltf = pygltflib.GLTF2(
        scene=0,
        scenes=[pygltflib.Scene(nodes=[0])],
        nodes=[pygltflib.Node(mesh=0)],
        meshes=[
            pygltflib.Mesh(
                primitives=[
                    pygltflib.Primitive(
                        attributes=pygltflib.Attributes(
                            POSITION=1, TEXCOORD_0=3, COLOR_0=2
                        ),
                        indices=0,
                        material=0
                    )
                ]
            )
        ],
        accessors=[
            pygltflib.Accessor(
                bufferView=0,
                componentType=pygltflib.UNSIGNED_SHORT,
                count=triangle_count,
                type=pygltflib.SCALAR,
                max=[triangle_minmax.max],
                min=[triangle_minmax.min],
            ),
            pygltflib.Accessor(
                bufferView=1,
                componentType=pygltflib.FLOAT,
                count=vertex_count,
                type=pygltflib.VEC3,
                max=list(vertex_minmax.max),
                min=list(vertex_minmax.min),
            ),
            pygltflib.Accessor(
                bufferView=1,
                componentType=pygltflib.UNSIGNED_BYTE,
                normalized=True,
                count=vertex_count,
                type=pygltflib.VEC3,
                byteOffset=13,
                max=list(color_minmax.max),
                min=list(color_minmax.min),
            ),
            pygltflib.Accessor(
                bufferView=1,
                componentType=pygltflib.FLOAT,
                normalized=True,
                count=vertex_count,
                type=pygltflib.VEC2,
                byteOffset=16,
                max=list(uv_minmax.max),
                min=list(uv_minmax.min),
            ),
        ],
        # materials=[
        #     # pygltflib.Material()
        # ],
        images=images,
        textures=textures,
        materials=materials,
        samplers=[
            pygltflib.Sampler(
                magFilter=pygltflib.LINEAR,
                minFilter=pygltflib.NEAREST_MIPMAP_LINEAR,
                wrapS=pygltflib.REPEAT,
                wrapT=pygltflib.REPEAT,
            )
        ],
        bufferViews=[
            pygltflib.BufferView(
                buffer=0,
                byteLength=len(triangle_io.getvalue()),
                target=pygltflib.ELEMENT_ARRAY_BUFFER,
            ),
            pygltflib.BufferView(
                buffer=0,
                byteOffset=len(triangle_io.getvalue()),
                byteLength=len(vertex_io.getvalue()),
                byteStride=24,
                target=pygltflib.ARRAY_BUFFER,
            ),
        ],
        buffers=[
            pygltflib.Buffer(
                byteLength=len(triangle_io.getvalue()) + len(vertex_io.getvalue())
            )
        ],
    )

    gltf.set_binary_blob(triangle_io.getvalue() + vertex_io.getvalue())

    validate(gltf)

    Path("test.gltf").write_bytes(
        b"".join(gltf.save_to_bytes())
    )

    # with Path("test.obj").open("w") as f:
    #     for vertex in model.vertex_store_setup_header.vertices:
    #         f.write(f"v {vertex.position[0] / 100} {vertex.position[1] / 100} {vertex.position[2] / 100}\n")

    #     faces = model.simulate_displaylist()

    #     for face in faces:
    #         f.write(f"f {face[0] + 1} {face[1] + 1} {face[2] + 1}\n")


@cli.command()
def convert_all_models():
    for path in Path("models").glob("*.bin"):
        model = Model.parse_bytes(path.read_bytes())

        new_path = Path(f"objs/{path.stem}.obj")
        new_path.parent.mkdir(exist_ok=True)

        with new_path.open("w") as f:
            for vertex in model.vertex_store_setup_header.vertices:
                f.write(f"v {vertex.position[0] / 100} {vertex.position[1] / 100} {vertex.position[2] / 100}\n")

            faces = model.simulate_displaylist()

            for face in faces:
                f.write(f"f {face[0] + 1} {face[1] + 1} {face[2] + 1}\n")

if __name__ == "__main__":
    cli()
