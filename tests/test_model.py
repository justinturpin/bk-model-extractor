from jtn64 import Model, ModelHeader
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
