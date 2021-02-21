from dataclasses import dataclass
from typing import List
from .f3d import Vertex


@dataclass
class Mesh:
    texture_index: int
    scale_s: float
    scale_t: float
    indices: List[int]
    vertices: List[Vertex]
