# HEIF reader prototype

This helper's Python source is covered by TransCora's MIT license. It runs as a
separate program; the main application must not import pillow-heif.

The investigated pillow-heif 1.8.1 binary wheel includes GPLv2 x265, LGPLv3
libheif and LGPLv3 libde265. The wrapper is BSD-3-Clause. A frozen helper built
with that wheel must be distributed under the applicable combined GPL terms,
with the exact corresponding source, build scripts and dependency notices.
The main application license does not replace these terms.

This is currently a development prototype, not a packaged component. Do not
add a frozen reader to a release until the source/build/license bundle and all
three platform tests are in place. Decoder-only LGPL builds remain an alternative.

Primary sources:

- https://github.com/bigcat88/pillow_heif/tree/v1.8.1
- https://github.com/bigcat88/pillow_heif/blob/v1.8.1/LICENSES_bundled.txt
- https://github.com/strukturag/libheif
- https://github.com/strukturag/libde265
- https://x265.org/legal-notices/
