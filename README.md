# BK Model Extractor

Extracts models from Banjo Kazooie ROMs into GLTF format.

## Usage

```bash
# Install dependencies with Poetry
poetry install

# Get into virtual environment
poetry shell

# Dump all ROM models to `models/`. This must be a big-endian ROM.
./decompile.py dump-models roms/bk_reswapped.n64

# Convert all models into GLTF format, storing into the gltf folder
./decompile.py dump-model-gltf models/*
```

## TODO

- [ ] Fix animated models. They look awful!
- [ ] Some UV's are just wrong and warped. I assume this is some F3D
      command I'm not emulating properly.
- [ ] GLTF's do not load properly in Godot or the Windows model viewer. They
      load fine in Blender and the online GLTF viewer.
- [ ] Reorganize the project a bit so that decompile.py has less GLTF logic in
      it.
