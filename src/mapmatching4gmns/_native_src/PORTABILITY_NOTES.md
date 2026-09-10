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
4. Replaced the MSVC-only `__int64` cell identifiers with standard `std::int64_t` and a
   portable `long long` cast at the CSV formatting boundary.
5. Native fatal paths raise a Python `RuntimeError` in extension builds instead of terminating
   the host process; the binding restores the process working directory with an RAII guard.
6. CSV headers and values are trimmed for spaces, tabs, LF, and CRLF. This prevents the final
   column name (`y_coord`, `geometry`, or `d_node_id`) from retaining a Windows carriage return.

## Status
- The package now uses scikit-build-core + CMake + pybind11 instead of hand-written Python
  include/library flags.
- Apple Silicon macOS + CPython 3.13 builds and runs both engines successfully.
- Linux, Windows, macOS Intel, and the remaining supported CPython versions are gated by the
  cibuildwheel matrix; support is claimed only after those installed-wheel tests pass.

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
- Future optimization: replace the temporary CSV transport with an in-memory
  `load_network`/`run` API behind the existing pybind11 boundary.

## Phase 4 (string link_id + parallel note)
- **link_id preserved as a STRING** in `route.csv` (was an int that dropped the AB/BA
  suffix, and collided AB/BA on the int key). Added `CLink.link_id_str`, read the full id,
  emit `%s` in the route output. Engine outputs now carry the full GMNS `link_id` (e.g.
  `193748AB`), directly comparable to the geometric engine -- no normalization needed.
  The int `link_id` is kept for internal indexing; a fuller fix would key
  `g_internal_link_no_map` by the string so the two directions never collide.
- **OpenMP is disabled for the 0.3.0 wheels.** It can be enabled for experimental source builds
  with `-Ccmake.define.MAPMATCHING4GMNS_OPENMP=ON` after each platform runtime is validated.
