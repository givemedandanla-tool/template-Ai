# Bundled Tesseract runtime: corresponding source and notices

Reviewed 2026-10-24 for the fixed UB-Mannheim Windows x64 installer 5.4.0.20240606, SHA256 c885fff6998e0608ba4bb8ab51436e1c6775c2bafc2559a19b423e18678b60c9. Scope is only tesseract.exe plus its 26 recursively imported non-system DLLs. Training executables, installer/uninstaller, PATH/registry helpers and unrelated DLLs are not shipped.

## Redistribution and source access

Tesseract upstream is Apache-2.0, but this Windows runtime is not Apache-only. Its libtiff imports JBIG-KIT 2.1, whose original jbig.c expressly permits GPL version 2 or any later version. The bundled linked CLI is distributed on the GPLv3-compatible route with the complete source attachment and GPLv3 text; original per-component copyright notices and licenses remain intact. libiconv is LGPL-2.1-or-later; GCC runtimes retain GPLv3 and GCC Runtime Library Exception 3.1. winpthreads retains MIT and BSD-3-Clause-Clear notices. This does not relicense the separate Python application as Apache or claim that every DLL has the same license.

The release provides TemplateAIReview-<version>-ocr-corresponding-source.zip alongside the Windows application. It contains the exact pinned source archives, full MSYS2 historical build recipes/patches, notices, provenance and both runtime/source inventories. Each archive is verified by byte count and SHA256; source attachment verification checks every inner source and notice again after draft and public download. No three-year mail offer or link to an unspecified newest source substitutes for these downloadable bytes.

Private artwork, customer text, local fonts, databases and user-trained models are not part of this source package. The bundled public eng/chi_tra language data has its separate official tessdata_fast pin and Apache license; it is not a private model. CLI execution is local and requires no administrator installer or network connection.

## Source provenance

Most objects are upstream release archives or fixed upstream commit archives. GNU libiconv 1.17 uses a fixed Winlibs vanilla release-source import with generated configure/build files plus a GNU author-history Git mirror crosscheck: all 704 common files are byte-identical, and the release import adds 332 generated files. JBIG-KIT 2.1 uses the fixed Deepin distribution source mirror, and the source license header was verified directly. giflib uses Debian's official unmodified orig.tar.gz, whose SHA256 is identical to the MSYS2 canonical upstream archive. These provenance records do not claim the GNU/Cambridge original compressed containers were downloaded or verified. Git archives have different root names and compression hashes from release tarballs.

The MSYS2 recipe snapshot is MINGW-packages c6674b1e3a9d8301b4e63bb1b1ca3d1ed81fe5bf (2024-06-06). Recipe byte identity was separately checked for GCC 14.1.0-3, winpthreads 12.0.0.r32.gf977e1c38, libiconv 1.17-4 and JBIG-KIT 2.1-5, including their patches. Other dependency versions are corroborated by the historical recipes and embedded binary version information where available; not every DLL contains a self-reported version. Binary identity itself is fixed by the runtime installer and every selected DLL hash, not inferred from a filename. This is source/provenance qualification, not a claim of byte-reproducible rebuilding or comprehensive OCR accuracy.

## Component map

| Component | Version | Runtime files | License basis |
|---|---|---|---|
| bzip2 | 1.0.8 | libbz2-1.dll | bzip2-1.0.6 |
| expat | 2.6.2 | libexpat-1.dll | MIT |
| gcc | 14.1.0 | libgcc_s_seh-1.dll, libstdc++-6.dll | GPL-3.0-or-later WITH GCC-exception-3.1 |
| giflib | 5.2.2 | libgif-7.dll | MIT |
| jbigkit | 2.1 | libjbig-0.dll | GPL-2.0-or-later, GPL-3.0 selected for linked runtime redistribution |
| leptonica | 1.84.1 | libleptonica-6.dll | BSD-2-Clause |
| lerc | 4.0.0 | libLerc.dll | Apache-2.0 |
| libarchive | 3.7.4 | libarchive-13.dll | BSD-2-Clause and included third-party notices |
| libb2 | 0.98.1 | libb2-1.dll | CC0-1.0 |
| libdeflate | 1.20 | libdeflate.dll | MIT |
| libiconv | 1.17 | libiconv-2.dll | LGPL-2.1-or-later for shared library; GPL tools not shipped |
| libjpeg-turbo | 3.0.3 | libjpeg-8.dll | BSD-3-Clause AND IJG AND Zlib (see complete upstream LICENSE.md/README.ijg) |
| libpng | 1.6.43 | libpng16-16.dll | libpng-2.0 |
| libtiff | 4.6.0 | libtiff-6.dll | MIT |
| libwebp | 1.4.0 | libwebp-7.dll, libwebpmux-3.dll, libsharpyuv-0.dll | BSD-3-Clause AND upstream patent grant |
| lz4 | 1.9.4 | liblz4.dll | BSD-2-Clause for library (upstream CLI GPL not shipped) |
| openjpeg | 2.5.2 | libopenjp2-7.dll | BSD-2-Clause |
| openssl | 3.3.1 | libcrypto-3-x64.dll | Apache-2.0 |
| tesseract | 5.4.0.20240606 | tesseract.exe, libtesseract-5.dll | Apache-2.0 upstream; bundled linked CLI contains GPL-2.0-or-later JBIG and uses GPL-3.0-compatible redistribution with corresponding source |
| winpthreads | 12.0.0.r32.gf977e1c38 | libwinpthread-1.dll | MIT AND BSD-3-Clause-Clear |
| xz | 5.6.2 | liblzma-5.dll | 0BSD for liblzma; other source files have licenses listed in COPYING |
| zlib | 1.3.1 | zlib1.dll | Zlib |
| zstd | 1.5.6 | libzstd.dll | BSD-3-Clause selected, upstream also offers GPL-2.0-or-later |
