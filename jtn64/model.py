from dataclasses import dataclass
from struct import unpack
from typing import List, Tuple
from . import textures
from .util import BitReader, print_hex
from .f3d import Vertex, F3DCommandType, F3DCommandGVtx, F3DCommandGTri1, \
    F3DCommandGTri2
from .textures import TextureType


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

        return TextureSetupHeader(
            data_length=data_length,
            texture_count=texture_count,
            texture_sub_headers=texture_sub_headers
        )


@dataclass
class TextureData:
    width: int
    height: int
    data: bytes
    texture_type: TextureType

    def to_rgba(self) -> List[Tuple[int, int, int, int]]:
        result = []

        if self.texture_type is TextureType.CI4:
            palette = textures.read_palette_rgb565(self.data)

            # Palette is 16 bits (2 bytes) per pixel, and there are 16
            # colors since its a 4 bit palette, so image data starts at 32
            reader = BitReader(self.data[16*2:])

            for i in range(self.width * self.height):
                result.append(palette[reader.read_sub(4)])
        elif self.texture_type is TextureType.RGBA16:
            reader = BitReader(self.data)

            for color in textures.iter_colors_rgb555a(self.data, self.width * self.height):
                result.append(color)
        elif self.texture_type is TextureType.IA8:
            for color in textures.iter_colors_ia8(self.data, self.width * self.height):
                result.append(color)

        return result


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
        print_hex(data[offset:offset + 2])

        vertex_count_doubled = unpack(">H", data[offset:offset + 2])[0]
        vertices = []

        print(f"vertex count doubled={vertex_count_doubled}")

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

    def simulate_displaylist(self):
        vertex_index_buffer = [0] * 64
        faces = []

        for command in self.display_list_setup_header.commands:
            if isinstance(command, F3DCommandGVtx):
                segment_offset = command.load_address & 0xFFFFFF

                index_offset = segment_offset // 16

                for i in range(command.verts_to_write):
                    vertex_index_buffer[command.write_start + i] = index_offset + i
            elif isinstance(command, F3DCommandGTri1):
                faces.append((
                    vertex_index_buffer[command.vertex_1],
                    vertex_index_buffer[command.vertex_2],
                    vertex_index_buffer[command.vertex_3],
                ))
            elif isinstance(command, F3DCommandGTri2):
                faces.append((
                    vertex_index_buffer[command.vertex_1],
                    vertex_index_buffer[command.vertex_2],
                    vertex_index_buffer[command.vertex_3],
                ))

                faces.append((
                    vertex_index_buffer[command.vertex_4],
                    vertex_index_buffer[command.vertex_5],
                    vertex_index_buffer[command.vertex_6],
                ))

        return faces
