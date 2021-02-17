from enum import IntEnum
from dataclasses import dataclass
from typing import List, Tuple
from struct import unpack


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


class F3DCommandType(IntEnum):
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

    G_UNKNOWN_1 = 185
    G_UNKNOWN_2 = 244


@dataclass
class F3DCommandGVtx:
    write_start: int
    verts_to_write: int
    vert_data_len: int
    load_address: int


@dataclass
class F3DCommandGTri1:
    vertex_1: int
    vertex_2: int
    vertex_3: int


@dataclass
class F3DCommandGTri2:
    vertex_1: int
    vertex_2: int
    vertex_3: int
    vertex_4: int
    vertex_5: int
    vertex_6: int
