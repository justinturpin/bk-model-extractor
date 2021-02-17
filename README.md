Format:
 - n64: little-endian
 - z64: big-endian
 - u64/v64: byte-swapped (see util.py for details)


Vertex format `{x, y, z, f, t, c, r, g, b, a}`

```c
typedef struct {
    short        ob[3];    /* x, y, z coordinates*/
    unsigned short    flag;
    short        tc[2];    /* texture coordinates */
    unsigned char    cn[4];    /* 3 color & alpha */
} Vtx_t;

typedef struct {
    short        ob[3];    /* x, y, z coordinates */
    unsigned short    flag;
    short        tc[2];    /* texture coordinates */
    signed char    n[3];    /* normal */
    unsigned char   a;      /* alpha  */
} Vtx_tn;

typedef union {
    Vtx_t        v;  /* Use this one for colors  */
    Vtx_tn              n;  /* Use this one for normals */
    long long int    force_structure_alignment;
} Vtx;
```

```
yeah
ok yeah, i think segAddr for VTX  is indeed just the vertex store directly
with it using segment 0x10
like the first set is set to no texture, and renders two quads using the first 5 verts
then loads another 4, and another 4 in a weird place, but its definitely just going down the vertex store
so i guess you could get a very basic model from:
- read the vertex store, which gives you the modern-like 'vertex buffer'
- read the displaylist, faking the vbuffer, and when you hit a TRI2, you map the two and that becomes your index buffer for a GL_TRIANGLES type
or whatever the triangles type is in OBJ
totally ignores textures and stuff, but that'd be a first pass
oh and data wise, the display list is literally just sets of 8 bytes, so you could teach your python program the few you care about pretty easily, and just skip any others
oh
i think i see how G_DL works
i was thinking it starts a display list, but i dont think it actually is
though hm, what maps into segment 0x30 then
cause thats the one draw thing its calling out to over and over again
ok yeah, its a function call
might be a good thing though - that means every block is basically independent
which is what a real model format would work like
```
