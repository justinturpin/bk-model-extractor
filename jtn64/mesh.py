from dataclasses import dataclass
from typing import List, Optional
from .f3d import Vertex


@dataclass
class Mesh:
    texture_index: Optional[int]
    indices: List[int]
    vertices: List[Vertex]
