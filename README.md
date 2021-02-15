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
