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
            texture_data_length = 2**4 + (width * height / 2)
        elif texture_type is TextureType.CI8:
            texture_data_length = 2**8 + (width * height)
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
            reader = BitReader(self.data[16*2])

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
class Model:
    model_header: ModelHeader
    texture_setup_header: TextureSetupHeader
    texture_data: List[TextureData]

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
            vert_count, \
            tri_count = unpack(
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
            vert_count=vert_count,
            tri_count=tri_count,
        )

        texture_setup_header = TextureSetupHeader.parse_bytes(
            data[model_header.texture_setup_offset:]
        )

        texture_data = []

        for sub_texture in texture_setup_header.texture_sub_headers:
            texture_data_start = (
                texture_setup_offset + sub_texture.segment_address_offset
            )

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

        return Model(
            model_header=model_header,
            texture_setup_header=texture_setup_header,
            texture_data=texture_data,
        )
