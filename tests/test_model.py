from jtn64 import Model, ModelHeader, TextureSetupHeader, TextureSubHeader
from struct import pack
from pathlib import Path


def test_parse_model():
    model_data = pack(
        ">IIIIIIIIIIIIHH",
        0x0B,
        100, 101, 102, 103,
        0x00,  # unused_1
        104, 105, 106, 107,
        0x00,  # unused_2
        0x00,  # unused_3
        900, 45
    )

    model = Model.parse_bytes(model_data)

    assert model.model_header.geometry_layout_offset == 100
    assert model.model_header.texture_setup_offset == 101
    assert model.model_header.display_list_setup_offset == 102
    assert model.model_header.vertex_store_setup_offset == 103
    assert model.model_header.tri_count == 900
    assert model.model_header.vert_count == 45


def test_parse_model_real():
    model_data = Path(
        Path(__file__).parent.parent, "models/2209552_model.bin"
    ).read_bytes()

    model = Model.parse_bytes(model_data)

    assert model.model_header == ModelHeader(
        geometry_layout_offset=20072,
        texture_setup_offset=0x38,
        display_list_setup_offset=4432,
        vertex_store_setup_offset=8184,
        animation_setup_offset=19696,
        collision_setup_offset=14208,
        vert_count=370,
        tri_count=274
    )

    print(model.texture_setup_header)


def test_texture_find_offset():
    header_1 = TextureSetupHeader(
        data_length=0,
        texture_count=2,
        texture_sub_headers=[
            TextureSubHeader(
                segment_address_offset=0x0,
                texture_type=1,
                width=32,
                height=32,
                texture_data_length=32*32*2
            ),
            TextureSubHeader(
                segment_address_offset=0x80,
                texture_type=1,
                width=32,
                height=32,
                texture_data_length=32*32*2
            ),
            TextureSubHeader(
                segment_address_offset=0xD0,
                texture_type=1,
                width=32,
                height=32,
                texture_data_length=32*32*2
            )
        ]
    )

    assert header_1.find_nearest_texture(0x0) == 0
    assert header_1.find_nearest_texture(0x10) == 0
    assert header_1.find_nearest_texture(0x40) == 0

    assert header_1.find_nearest_texture(0x80) == 1
    assert header_1.find_nearest_texture(0x90) == 1
    assert header_1.find_nearest_texture(0xA0) == 1

    assert header_1.find_nearest_texture(0xD0) == 2
    assert header_1.find_nearest_texture(0xD1) == 2
    assert header_1.find_nearest_texture(0xD2) == 2

    header_2 = TextureSetupHeader(
        data_length=0,
        texture_count=2,
        texture_sub_headers=[
            TextureSubHeader(
                segment_address_offset=0x0,
                texture_type=1,
                width=32,
                height=32,
                texture_data_length=32*32*2
            ),
        ]
    )

    assert header_2.find_nearest_texture(0x0) == 0
    assert header_2.find_nearest_texture(0x10) == 0
