cmake_minimum_required(VERSION 3.15)
project(mapmatching4gmns LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(PYBIND11_FINDPYTHON ON)

find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(
    _native
    bindings.cpp
    trace2route.cpp
)

target_compile_definitions(
    _native
    PRIVATE
        MM_PYBIND
        NOMINMAX
        MAPMATCHING4GMNS_VERSION="${SKBUILD_PROJECT_VERSION}"
)

if(MSVC)
    target_compile_definitions(_native PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()

option(MAPMATCHING4GMNS_OPENMP "Build the native engine with OpenMP" OFF)
if(MAPMATCHING4GMNS_OPENMP)
    find_package(OpenMP REQUIRED)
    target_link_libraries(_native PRIVATE OpenMP::OpenMP_CXX)
endif()

install(
    TARGETS _native
    LIBRARY DESTINATION mapmatching4gmns
    RUNTIME DESTINATION mapmatching4gmns
    ARCHIVE DESTINATION mapmatching4gmns
)
