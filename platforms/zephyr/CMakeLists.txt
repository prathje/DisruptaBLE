cmake_minimum_required(VERSION 3.13.1)
include($ENV{ZEPHYR_BASE}/cmake/app/boilerplate.cmake NO_POLICY_SCOPE)
project(ud3tn)



FILE(GLOB app_components ../../components/*/*.c ../../components/*/zephyr/*.c ../../components/routing/*/*.c)
FILE(GLOB app_include ../../include)





FILE(GLOB ext_src_tinycbor
        ../../external/tinycbor/src/cborencoder.c
        ../../external/tinycbor/src/cborencoder_close_container_checked.c
        ../../external/tinycbor/src/cborerrorstrings.c
        ../../external/tinycbor/src/cborparser.c
        ../../external/tinycbor/src/cborparser_dup_string.c
        ../../external/tinycbor/src/cborpretty.c
        ../../external/tinycbor/src/cborpretty_stdio.c
        ../../external/tinycbor/src/cbortojson.c
        ../../external/tinycbor/src/cborvalidation.c
)


FILE(GLOB ext_src ../../external/util/src/*.c)
FILE(GLOB ext_include ../../external/tinycbor/src ../../external/util/include)

target_sources(app PRIVATE ${app_components} ${ext_src} ${ext_src_tinycbor})

target_include_directories(app PRIVATE ${app_include} ${ext_include})
target_compile_definitions(app PUBLIC PLATFORM_ZEPHYR WITHOUT_OPEN_MEMSTREAM _POSIX_C_SOURCE=200809L)

