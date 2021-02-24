
from PIL import Image
from dataclasses import dataclass
from struct import unpack
from typing import List, Tuple
from . import textures
from .util import BitReader, print_hex, print_bin
from .f3d import Vertex, F3DCommandType, F3DCommandGVtx, F3DCommandGTri1, \
    F3DCommandGTri2, F3DCommandGTexture, F3DCommandSetTImg, \
    F3DCommandSetTImgTextureFormat
from .textures import TextureType
from .mesh import Mesh


@dataclass
class ModelHeader:
    """
    Descriptions from https://hack64.net/wiki/doku.php?id=banjo_kazooie:model_data
    """

    geometry_layout_offset: int
    texture_setup_offset: int
    display_list_setup_offset: int
    vertex_store_setup_offset: int
    animation_setup_offset: int
    collision_setup_offset: int
    vert_count: int
    tri_count: int


@dataclass
class TextureSubHeader:
    segment_address_offset: int
    texture_type: TextureType
    width: int
    height: int
    texture_data_length: int

    @classmethod
    def parse_bytes(cls: 'TextureSubHeader', data: bytes) -> 'TextureSubHeader':
        segment_address_offset, texture_type = unpack(">IH", data[0:6])
        width, height = unpack(">BB", data[8:10])
        texture_type = TextureType(texture_type)

        if texture_type is TextureType.CI4:
            texture_data_length = (2 * 2**4) + (width * height / 2)
        elif texture_type is TextureType.CI8:
            texture_data_length = (2 * 2**8) + (width * height)
        elif texture_type is TextureType.RGBA16:
            texture_data_length = width * height * 2
        elif texture_type is TextureType.RGBA32:
            texture_data_length = width * height * 4
        elif texture_type is TextureType.IA8:
            texture_data_length = width * height

        return TextureSubHeader(
            segment_address_offset=segment_address_offset,
            texture_type=texture_type,
            width=width,
            height=height,
            texture_data_length=int(texture_data_length)
        )


@dataclass
class TextureSetupHeader:
    data_length: int
    texture_count: int
    texture_sub_headers: List[TextureSubHeader]

    @classmethod
    def parse_bytes(cls: 'TextureSetupHeader', data: bytes) -> 'TextureSetupHeader':
        data_length, texture_count = unpack(">IH", data[0:6])

        texture_sub_headers = []

        for i in range(texture_count):
            sub_start = 8 + (i * 16)
            sub_end = sub_start + 16

            texture_sub_header_data = data[sub_start:sub_end]

            texture_sub_headers.append(
                TextureSubHeader.parse_bytes(texture_sub_header_data)
            )

        texture_sub_headers.sort(key=lambda x: x.segment_address_offset)

        return TextureSetupHeader(
            data_length=data_length,
            texture_count=texture_count,
            texture_sub_headers=texture_sub_headers
        )

    def find_nearest_texture(self, segment_address: int):
        # TODO: this could be a binary search and make Google interviwers happy.

        nearest = None

        for i, texture in enumerate(self.texture_sub_headers):
            if texture.segment_address_offset <= segment_address:
                nearest = i
            else:
                break

        return nearest


@dataclass
class TextureData:
    width: int
    height: int
    data: bytes
    texture_type: TextureType

    def to_rgba(self) -> List[Tuple[int, int, int, int]]:
        result = []

        if self.texture_type is TextureType.CI4:
            # TODO: you need information from the display list in order
            # to tell if this is 565 or 555a
            # palette = textures.read_palette_rgb565(self.data)
            palette = textures.read_palette_rgb555a(self.data)

            # Palette is 16 bits (2 bytes) per pixel, and there are 16
            # colors since its a 4 bit palette, so image data starts at 32
            reader = BitReader(self.data[16*2:])

            for i in range(self.width * self.height):
                color_index = reader.read_sub(4)

                result.append(palette[color_index])
        elif self.texture_type is TextureType.RGBA16:
            reader = BitReader(self.data)

            for color in textures.iter_colors_rgb555a(self.data, self.width * self.height):
                result.append(color)
        elif self.texture_type is TextureType.IA8:
            for color in textures.iter_colors_ia8(self.data, self.width * self.height):
                result.append(color)

        return result

    def to_image(self) -> Image:
        image = Image.new('RGBA', (self.width, self.height))

        for p, color in enumerate(self.to_rgba()):
            # y = self.height - (p // self.width) - 1
            y = p // self.width
            x = p % self.width

            image.putpixel((x, y), color)

        return image


@dataclass
class DisplayListSetupHeader:
    command_count: int
    commands: list

    @classmethod
    def parse_bytes(cls: 'DisplayListSetupHeader', data: bytes) -> 'DisplayListSetupHeader':
        command_count = unpack(">I", data[0:4])[0]
        commands = []

        for i in range(command_count):
            command_data = data[i*8 + 8:i*8 + 16]

            command_type = F3DCommandType(command_data[0])

            if command_type is F3DCommandType.G_VTX:
                # [II] [xx xx] [SS SS SS SS]
                write_start, \
                    vert_len, \
                    load_address = unpack(">BHI", command_data[1:])

                verts_to_write = vert_len >> 10
                vert_data_len = vert_len & 0b0000001111111111

                commands.append(
                    F3DCommandGVtx(
                        write_start=write_start,
                        verts_to_write=verts_to_write,
                        vert_data_len=vert_data_len,
                        load_address=load_address
                    )
                )
            elif command_type is F3DCommandType.G_TRI1:
                commands.append(
                    F3DCommandGTri1(
                        vertex_1=command_data[5] // 2,
                        vertex_2=command_data[6] // 2,
                        vertex_3=command_data[7] // 2,
                    )
                )
            elif command_type is F3DCommandType.G_TRI2:
                commands.append(
                    F3DCommandGTri2(
                        vertex_1=command_data[1] // 2,
                        vertex_2=command_data[2] // 2,
                        vertex_3=command_data[3] // 2,
                        vertex_4=command_data[5] // 2,
                        vertex_5=command_data[6] // 2,
                        vertex_6=command_data[7] // 2,
                    )
                )
            elif command_type is F3DCommandType.G_TEXTURE:
                s, t = unpack(">HH", command_data[4:8])

                commands.append(
                    F3DCommandGTexture(
                        scaling_factor_s=s / 2**16,
                        scaling_factor_t=t / 2**16,
                    )
                )
            elif command_type is F3DCommandType.G_SETTIMG:
                format_size = command_data[1]

                texture_format = F3DCommandSetTImgTextureFormat(
                    format_size >> 5
                )
                texture_bit_size = (format_size >> 3) & 0b11

                segment_address = unpack(">I", command_data[4:8])[0]

                commands.append(
                    F3DCommandSetTImg(
                        texture_segment_address=segment_address,
                        texture_bit_size=texture_bit_size,
                        texture_format=texture_format,
                    )
                )

        return DisplayListSetupHeader(
            command_count=command_count,
            commands=commands
        )


@dataclass
class VertexStoreSetupHeader:
    vertices: List[Vertex]

    @classmethod
    def parse_bytes(cls: 'VertexStoreSetupHeader', data: bytes) -> 'VertexStoreSetupHeader':
        offset = 6 + 6 + 4 + 2 + 2

        vertex_count_doubled = unpack(">H", data[offset:offset + 2])[0]
        vertices = []

        for i in range(vertex_count_doubled):
            start_offset = 0x18 + i * 16
            end_offset = start_offset + 16

            vertices.append(
                Vertex.from_bytes(data[start_offset:end_offset])
            )

        return VertexStoreSetupHeader(
            vertices=vertices
        )


@dataclass
class Model:
    """
    Represents the whole 3D Model.
    """

    model_header: ModelHeader

    texture_setup_header: TextureSetupHeader
    texture_data: List[TextureData]

    display_list_setup_header: DisplayListSetupHeader
    vertex_store_setup_header: VertexStoreSetupHeader

    @classmethod
    def parse_bytes(cls: 'Model', data: bytes) -> 'Model':
        start, \
            geometry_layout_offset, \
            texture_setup_offset, \
            _geo_type, \
            display_list_setup_offset, \
            vertex_store_setup_offset, \
            _unused_1, \
            animation_setup_offset, \
            collision_setup_offset, \
            _effects_setup_end_address, \
            _effects_setup_offset, \
            _unused_2, \
            _unused_3, \
            tri_count, \
            vert_count = unpack(
                ">IIHHIIIIIIIIIHH", data[0:52]
            )

        if start != 0x0B:
            raise ValueError(f"Invalid magic byte, got {start:x}")

        model_header = ModelHeader(
            geometry_layout_offset=geometry_layout_offset,
            texture_setup_offset=texture_setup_offset,
            display_list_setup_offset=display_list_setup_offset,
            vertex_store_setup_offset=vertex_store_setup_offset,
            animation_setup_offset=animation_setup_offset,
            collision_setup_offset=collision_setup_offset,
            tri_count=tri_count,
            vert_count=vert_count,
        )

        texture_setup_header = TextureSetupHeader.parse_bytes(
            data[model_header.texture_setup_offset:]
        )

        texture_data = []

        for sub_texture in texture_setup_header.texture_sub_headers:
            texture_data_start = texture_setup_offset \
                + sub_texture.segment_address_offset \
                + 8 \
                + (texture_setup_header.texture_count * 16)

            texture_data_end = (
                texture_data_start + sub_texture.texture_data_length
            )

            texture_data.append(
                TextureData(
                    width=sub_texture.width,
                    height=sub_texture.height,
                    texture_type=sub_texture.texture_type,
                    data=data[texture_data_start:texture_data_end]
                )
            )

        display_list_setup_header = DisplayListSetupHeader.parse_bytes(
            data[display_list_setup_offset:]
        )

        vertex_store_setup_header = VertexStoreSetupHeader.parse_bytes(
            data[vertex_store_setup_offset:]
        )

        return Model(
            model_header=model_header,
            texture_setup_header=texture_setup_header,
            texture_data=texture_data,
            display_list_setup_header=display_list_setup_header,
            vertex_store_setup_header=vertex_store_setup_header
        )

    def simulate_displaylist(self) -> List[Mesh]:
        """
        Walk through the display list and render a list of Meshes.
        """

        meshes = []
        vertex_index_buffer = [0] * 64

        scaling_factor_s = 1.0
        scaling_factor_t = 1.0

        touched_vertices = set()

        current_mesh = Mesh(
            texture_index=None,
            scale_s=1.0,
            scale_t=1.0,
            indices=[],
            vertices=[]
        )

        def _scale_vertex_uv(index):
            if index not in touched_vertices:
                # print(f"scaling vertex {index} by {scaling_factor_s}x{scaling_factor_t}")

                self.vertex_store_setup_header.vertices[index].uv[0] *= scaling_factor_s
                self.vertex_store_setup_header.vertices[index].uv[1] *= scaling_factor_t

                touched_vertices.add(index)

        for command in self.display_list_setup_header.commands:
            if isinstance(command, F3DCommandGVtx):
                # G_VTX

                segment_offset = command.load_address & 0xFFFFFF

                index_offset = segment_offset // 16

                for i in range(command.verts_to_write):
                    vertex_index_buffer[command.write_start + i] = index_offset + i
            elif isinstance(command, F3DCommandGTri1):
                # G_TRI1

                current_mesh.indices.append((
                    vertex_index_buffer[command.vertex_1],
                    vertex_index_buffer[command.vertex_2],
                    vertex_index_buffer[command.vertex_3],
                ))

                _scale_vertex_uv(command.vertex_1)
                _scale_vertex_uv(command.vertex_2)
                _scale_vertex_uv(command.vertex_3)

            elif isinstance(command, F3DCommandGTri2):
                # G_TRI2

                current_mesh.indices.append((
                    vertex_index_buffer[command.vertex_1],
                    vertex_index_buffer[command.vertex_2],
                    vertex_index_buffer[command.vertex_3],
                ))

                current_mesh.indices.append((
                    vertex_index_buffer[command.vertex_4],
                    vertex_index_buffer[command.vertex_5],
                    vertex_index_buffer[command.vertex_6],
                ))

                _scale_vertex_uv(command.vertex_1)
                _scale_vertex_uv(command.vertex_2)
                _scale_vertex_uv(command.vertex_3)
                _scale_vertex_uv(command.vertex_4)
                _scale_vertex_uv(command.vertex_5)
                _scale_vertex_uv(command.vertex_6)

            elif isinstance(command, F3DCommandSetTImg):
                # G_SETTIMG (Set texture image)

                # Every time we hit a SETTIMG, just start a new mesh.

                texture_offset = command.texture_segment_address - 0x02000000
                texture_index = self.texture_setup_header.find_nearest_texture(texture_offset)

                if texture_index != current_mesh.texture_index:
                    if current_mesh.indices:
                        meshes.append(current_mesh)

                    current_mesh = Mesh(
                        texture_index=texture_index,
                        scale_s=1.0,
                        scale_t=1.0,
                        indices=[],
                        vertices=[]
                    )

            elif isinstance(command, F3DCommandGTexture):
                scaling_factor_s = command.scaling_factor_s
                scaling_factor_t = command.scaling_factor_t

        if current_mesh and current_mesh.indices:
            meshes.append(current_mesh)

        return meshes
