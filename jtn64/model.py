from dataclasses import dataclass
from enum import IntEnum
from struct import unpack
from typing import List, Tuple
from . import textures
from .util import BitReader


class TextureType(IntEnum):
    CI4 = 1
    CI8 = 2
    RGBA16 = 4
    IA8 = 16


class F3DCommand(IntEnum):
    G_SPNOOP = 0x00
    G_MTX = 0x01
    G_VTX = 0x04
    G_DL = 0x06
    G_LOAD_UCODE = 0xAF
    G_SetOtherMode_H = 0xBA
    G_TRI2 = 0xB1
    G_TRI1 = 0xBF
    G_QUAD = 0xB5
    G_CLEARGEOMETRYMODE = 0xB6
    G_SETGEOMETRYMODE = 0xB7
    G_ENDDL = 0xB8
    G_TEXTURE = 0xBB
    G_POPMTX = 0xBD
    G_RDPLOADSYNC = 0xE6
    G_RDPPIPESYNC = 0xE7
    G_LOADTLUT = 0xF0
    G_SETTILESIZE = 0xF2
    G_LOADBLOCK = 0xF3
    G_SETCOMBINE = 0xFC
    G_SETTIMG = 0xFD
    G_SETTILE = 0xF5


@dataclass
class Vertex:
    position: Tuple[int, int, int]
    flag: int
    uv: Tuple[int, int]
    rgb_or_norm: Tuple[int, int, int]
    alpha: int

    @classmethod
    def from_bytes(cls: 'Vertex', data: bytes) -> 'Vertex':
        p_x, p_y, p_z, \
            flag, \
            uv_x, uv_y, \
            r, g, b, \
            alpha = unpack(
                ">hhhHhhBBBB",
                data
            )

        return Vertex(
            position=(p_x, p_y, p_z),
            flag=flag,
            uv=(uv_x, uv_y),
            rgb_or_norm=(r, g, b),
            alpha=alpha
        )


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
    commands: List[F3DCommand]

    @classmethod
    def parse_bytes(cls: 'DisplayListSetupHeader', data: bytes) -> 'DisplayListSetupHeader':
        command_count = unpack(">I", data[0:4])[0]
        commands = []

        for i in range(command_count):
            command_data = data[i*8 + 8:i*8 + 16]

            commands.append(F3DCommand(command_data[0]))

        return DisplayListSetupHeader(
            command_count=command_count,
            commands=commands
        )


@dataclass
class VertexStoreSetupHeader:
    vertices: List[Vertex]

    @classmethod
    def parse_bytes(cls: 'VertexStoreSetupHeader', data: bytes) -> 'VertexStoreSetupHeader':
        vertex_count_doubled = unpack(">H", data[0x16:0x18])[0]
        vertices = []

        for i in range(vertex_count_doubled // 2):
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
