#!/usr/bin/env python3

import zlib
import struct
import click
import io
import math

from pathlib import Path
from PIL import Image
import jtn64
from jtn64 import read_palette_rgb565, print_hex, BitReader, \
    iter_colors_rgb5a3, iter_colors_rgb565, iter_colors_rgb555a, \
    iter_colors_ia8, Model

import pygltflib


class MinMaxTracker:
    def __init__(self):
        self.min = None
        self.max = None

    def add(self, v):
        if self.min is None:
            self.min = v
        elif v < self.min:
            self.min = v

        if self.max is None:
            self.max = v
        elif v > self.max:
            self.max = v


class BoundingBoxTracker:
    def __init__(self):
        self.min = None
        self.max = None

    def add(self, v):
        if self.min is None:
            self.min = list(v)
        else:
            for i, x in enumerate(v):
                if x < self.min[i]:
                    self.min[i] = x

        if self.max is None:
            self.max = list(v)
        else:
            for i, x in enumerate(v):
                if x > self.max[i]:
                    self.max[i] = x


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
    """
    Finds models from rom data. Scans the entire ROM looking for
    the Zlib header (0x1172) and then attempts to decompress it.
    """

    model_count = 0

    for i in range(len(rom_data) - 17):
        a = rom_data[i]
        b = rom_data[i + 1]

        if a == 0x11 and b == 0x72:
            size = int.from_bytes(rom_data[i + 2:i + 6], byteorder='big')

            # If it's greater than 5mb, it's probably not a valid object.
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

                        # print_hex(decompressed[0:0x38])

                        print(f"Triangle_count={triangle_count}, vertex_count={vertex_count}")

                        model_path = Path(f"models/{i:08x}_model.bin")

                        print(f"Writing to {model_path}")

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
@click.argument("rom-path")
def dump_models(rom_path: str):
    """
    Dump models from a Banjo Kazooie normal (big endian) ROM file
    into a folder called `roms`.
    """

    rom = Path(rom_path)

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
@click.argument("paths", nargs=-1)
def dump_model_gltf(paths: str):
    for path in paths:
        path = Path(path)
        model = Model.parse_bytes(path.read_bytes())

        print("--------------------------")
        print(f"  Command count={model.display_list_setup_header.command_count}")
        print(f'  tris={model.model_header.tri_count}, verts={model.model_header.vert_count}')
        print(f'  texture count={model.texture_setup_header.texture_count}')

        if model.model_header.tri_count == 0:
            continue

        images = []
        textures = []
        materials = []
        nodes = []
        scene_nodes = []
        accessors = []

        vertex_io = io.BytesIO()
        triangle_io = io.BytesIO()

        vertex_count = 0

        vertex_minmax = BoundingBoxTracker()
        color_minmax = BoundingBoxTracker()
        uv_minmax = BoundingBoxTracker()

        try:
            model_meshes = model.simulate_displaylist()
        except Exception as e:
            print(e)

            continue

        gltf_meshes = []

        position_accessor_index = len(model_meshes)
        color_accessor_index = len(model_meshes) + 1
        uv_accessor_index = len(model_meshes) + 2

        for mesh_index, mesh in enumerate(model_meshes):
            triangle_minmax = MinMaxTracker()
            byte_offset = len(triangle_io.getvalue())

            print(f'Mesh: texture_index={mesh.texture_index}, tri_count={len(mesh.indices)}')

            scene_nodes.append(mesh_index)

            gltf_meshes.append(
                pygltflib.Mesh(
                    primitives=[
                        pygltflib.Primitive(
                            attributes=pygltflib.Attributes(
                                POSITION=position_accessor_index,
                                COLOR_0=color_accessor_index,
                                TEXCOORD_0=uv_accessor_index,
                            ),
                            indices=mesh_index,
                            material=mesh.texture_index
                        )
                    ]
                )
            )

            nodes.append(
                pygltflib.Node(
                    mesh=mesh_index,
                    name=f"mesh_{mesh_index}"
                )
            )

            for face_index, face in enumerate(mesh.indices):
                triangle_io.write(struct.pack("HHH", *face))

                triangle_minmax.add(face[0])
                triangle_minmax.add(face[1])
                triangle_minmax.add(face[2])

            accessors.append(
                pygltflib.Accessor(
                    bufferView=0,
                    componentType=pygltflib.UNSIGNED_SHORT,
                    byteOffset=byte_offset,
                    count=len(mesh.indices)*3,
                    type=pygltflib.SCALAR,
                    max=[triangle_minmax.max],
                    min=[triangle_minmax.min],
                )
            )

        # Pad to 4 bytes
        while len(triangle_io.getvalue()) % 4 != 0:
            triangle_io.write(struct.pack("B", 0))

        for vertex_index, vertex in enumerate(model.vertex_store_setup_header.vertices):
            position = (
                vertex.position[0] / 128,
                vertex.position[1] / 128,
                vertex.position[2] / 128
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
            vertex_io.write(struct.pack("BBBB", *color, 0))
            vertex_io.write(struct.pack("ff", *uv))

            vertex_minmax.add(position)
            color_minmax.add(color)
            uv_minmax.add(uv)

            vertex_count += 1

        # Pad to 4 bytes
        while len(vertex_io.getvalue()) % 4 != 0:
            vertex_io.write(struct.pack("B", 0))

        # Add the vertex accessors (position, color, then UV)

        accessors += [
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
                byteOffset=12,
                max=list(color_minmax.max),
                min=list(color_minmax.min),
            ),
            pygltflib.Accessor(
                bufferView=1,
                componentType=pygltflib.FLOAT,
                count=vertex_count,
                type=pygltflib.VEC2,
                byteOffset=16,
                max=list(uv_minmax.max),
                min=list(uv_minmax.min),
            ),
        ]

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
                        baseColorTexture=pygltflib.TextureInfo(index=i),
                        metallicFactor=0.0
                    ),
                    name=f"texture_{i}",
                    alphaMode=pygltflib.MASK
                )
            )

        gltf = pygltflib.GLTF2(
            scene=0,
            scenes=[pygltflib.Scene(nodes=scene_nodes)],
            nodes=nodes,
            meshes=gltf_meshes,
            accessors=accessors,
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
                    byteOffset=0,
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

        outpath = Path(f"gltf/{path.stem}.gltf")
        outpath.parent.mkdir(exist_ok=True)

        outpath.write_bytes(
            b"".join(gltf.save_to_bytes())
        )


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
