# Portability changes (MSVC -> g++/clang), Phase 1

Applied to make Zhou's trace2route.cpp cross-platform (Windows/macOS/Linux):

1. `stdafx.h` -> portable shim (this folder): dropped MFC (`afx*.h`, `tchar.h`); added
   `<cstdio> <cstring> <cstdlib> <cassert>`, `TRACE(...)->no-op`, `ASSERT->assert`, and
   mixed-type `max`/`min` templates (MSVC allows `max(int,size_t)` etc.; standard C++ does
   not -- SFINAE-disabled for same-type so `std::max`/`min` still win there).
2. Removed `getchar()` from the exit path (blocks in library/CI use).
3. **Bug found + fixed** (trace2route.cpp ~L3242, g_OutputAgentCSVFile):
   `p_agent->distance += fprintf(g_pFileAgent, "%s,");` -- an **argument-less `%s`** (reads
   garbage -> `strlen` crash on glibc/MinGW; MSVC printed `(null)`), AND the `distance +=`
   erroneously stored the fprintf return into the agent distance. Replaced with a plain
   column write. This is a real correctness bug, not just portability.

## Status
- Compiles clean with g++ (would build on clang/Mac/Linux -- pure STL now).
- Runs at -O0: exit 0, valid matched route (30 links on the sample).
- **Open (Phase 2):** an -O2 optimization-sensitive crash remains (residual UB in the
  legacy globals/output path). Fix during the I/O-vs-compute split, then enable -O2.

## Phase 2 (controlled memory + reusable) -- DONE
- **Corrected the Phase-1 "-O2 UB" finding:** it was NOT undefined behavior. It was a
  runtime **libstdc++ DLL/ABI mismatch** -- a binary built against WinLibs libstdc++ loaded
  Git's older `libstdc++-6.dll` (crash inside `ifstream`'s ctor). Fix = **static linking**
  (`-static -static-libstdc++ -static-libgcc`), which we want for distribution anyway.
  `-O2 static` now runs clean and byte-identical to `-O0`.
- **`mm_reset_state()`** clears all per-run global state (node/link/agent vectors, the six
  internal maps, counters) and **`delete[] g_pNetworkVector`** -- the shortest-path network
  array was allocated with `new[]` every run and never freed (the biggest leak).
- **`mm_run_once()`** replaces the `exit(0)`/`getchar()` `main`: resets, reads, matches,
  writes, tears down, and **returns** -- so a host (pybind11 / CLI / batch loop) calls it
  repeatedly in one process. `main` gains `--selftest-twice`.
- **Verified:** `./trace2route --selftest-twice` runs two matches in one process, exit 0,
  no crash, run-2 output IDENTICAL to run-1 -> controlled memory, no state bleed.

## Remaining (before wide distribution)
- Complete `~NetworkForSP()` to free `m_GridMatrix` + the `m_TD_*` 2D arrays (add a
  `Deallocate2DDynamicArray` helper) -- a residual, slow leak over many runs (does not
  affect correctness or cause state bleed).
- Replace MSVC `__int64` (cell-id maps, ~L67-68) with `int64_t` for clang/macOS.
- Phase 3: an in-memory API (`load_network`/`run` taking arrays, returning result structs)
  + pybind11 binding, so no temp-CSV round-trip.

## Phase 4 (string link_id + parallel note)
- **link_id preserved as a STRING** in `route.csv` (was an int that dropped the AB/BA
  suffix, and collided AB/BA on the int key). Added `CLink.link_id_str`, read the full id,
  emit `%s` in the route output. Engine outputs now carry the full GMNS `link_id` (e.g.
  `193748AB`), directly comparable to the geometric engine -- no normalization needed.
  The int `link_id` is kept for internal indexing; a fuller fix would key
  `g_internal_link_no_map` by the string so the two directions never collide.
- **OpenMP (parallel batch) is present but disabled.** `new NetworkForSP[number_of_threads]`
  makes a per-thread network copy for shortest-path; `#include <omp.h>` + the
  `#pragma omp parallel for` on the agent loop are commented out. Re-enable + build with
  `-fopenmp` to parallelize a large sample batch across cores (serialize the route.csv write).
