#!/usr/bin/env bash
# Build the cross-platform in-process Python module mapmatching4gmns_engine (Phase 3).
# CRITICAL on Windows/MinGW vs MSVC-built CPython: use full -static (statically links
# libwinpthread/libgcc/libstdc++) or the .pyd imports with "DLL load failed".
set -e
CXX=${CXX:-g++}
PYINC=$(python -c "import sysconfig;print(sysconfig.get_path('include'))")
PBINC=$(python -c "import pybind11;print(pybind11.get_include())")
EXT=$(python -c "import sysconfig;print(sysconfig.get_config_var('EXT_SUFFIX') or '.pyd')")
# Opt-in OpenMP: MM_OPENMP=1 enables the parallel agent loop (per-thread NetworkForSP copies).
# Default OFF -> serial, byte-identical to the verified single-thread behavior. The engine is
# thread-safe (per-network match markers), but the parallel loop only exists when -fopenmp is
# compiled AND CORRIDOR2GMNS_MM_THREADS>1 at runtime.
OMP=""
if [ "${MM_OPENMP:-0}" = "1" ]; then OMP="-fopenmp"; echo "OpenMP build (parallel agent loop enabled)"; fi
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)  # Windows
    PYLIB="$(python -c "import sys,os;print(os.path.join(sys.base_prefix,'libs'))")"
    $CXX -O2 -std=c++14 -w -shared -static -static-libstdc++ -static-libgcc $OMP -DMM_PYBIND \
      -I"$PYINC" -I"$PBINC" bindings.cpp trace2route.cpp \
      -o "mapmatching4gmns_engine${EXT}" -L"$PYLIB" -lpython311 ;;
  *)  # macOS / Linux (clang or g++); Python symbols resolve at load time
    $CXX -O2 -std=c++14 -w -shared -fPIC $OMP -undefined dynamic_lookup -DMM_PYBIND \
      -I"$PYINC" -I"$PBINC" bindings.cpp trace2route.cpp \
      -o "mapmatching4gmns_engine${EXT}" 2>/dev/null || \
    $CXX -O2 -std=c++14 -w -shared -fPIC $OMP -DMM_PYBIND \
      -I"$PYINC" -I"$PBINC" bindings.cpp trace2route.cpp -o "mapmatching4gmns_engine${EXT}" ;;
esac
echo "built mapmatching4gmns_engine${EXT}${OMP:+ (with $OMP)}"
