// pybind11 binding for Zhou's MapMatching4GMNS (trace2route) -- Phase 3.
// Cross-platform, in-process Python module: no exe subprocess. The reusable mm_run_once()
// (Phase 2) is called in a working directory that holds node/link/trace CSV, and route.csv
// is parsed back into Python objects. Build fully static (-static) so the .pyd/.so has no
// MinGW runtime-DLL dependency (see build_pybind.sh).
//
// This first cut keeps CSV as the in-process transport (the Python caller writes the three
// CSVs, same as the exe path). A later optimization can populate the engine's structures
// from arrays directly (true zero-CSV) behind the SAME Python API.
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <fstream>
#include <map>
#include <string>
#include <vector>

#ifdef _WIN32
#include <direct.h>
#define MM_GETCWD _getcwd
#define MM_CHDIR _chdir
#else
#include <unistd.h>
#define MM_GETCWD getcwd
#define MM_CHDIR chdir
#endif

extern int mm_run_once();        // trace2route.cpp (Phase 2): reusable, returns status
extern void mm_reset_state();

namespace py = pybind11;

// split a CSV line respecting double-quoted fields (geometry contains commas)
static std::vector<std::string> split_csv(const std::string& line) {
    std::vector<std::string> out;
    std::string cur;
    bool in_q = false;
    for (char c : line) {
        if (c == '"') { in_q = !in_q; cur.push_back(c); }
        else if (c == ',' && !in_q) { out.push_back(cur); cur.clear(); }
        else cur.push_back(c);
    }
    out.push_back(cur);
    return out;
}

// Run the matcher in `work_dir` (must contain node.csv, link.csv, trace.csv) and return
// route.csv as a list of dict {column: value}. In-process; no subprocess.
static std::vector<std::map<std::string, std::string>> run_in_dir(const std::string& work_dir) {
    char cwd[4096] = {0};
    if (MM_GETCWD(cwd, sizeof(cwd)) == nullptr) throw std::runtime_error("getcwd failed");
    if (MM_CHDIR(work_dir.c_str()) != 0) { throw std::runtime_error("chdir failed: " + work_dir); }

    int rc;
    {
        py::gil_scoped_release release;   // long compute -> let other Python threads run
        rc = mm_run_once();
    }

    std::vector<std::map<std::string, std::string>> rows;
    {
        std::ifstream f("route.csv");
        std::string header, line;
        if (std::getline(f, header)) {
            std::vector<std::string> cols = split_csv(header);
            while (std::getline(f, line)) {
                if (line.empty()) continue;
                std::vector<std::string> vals = split_csv(line);
                std::map<std::string, std::string> row;
                for (size_t i = 0; i < cols.size() && i < vals.size(); ++i) row[cols[i]] = vals[i];
                rows.push_back(row);
            }
        }
    }
    MM_CHDIR(cwd);          // restore
    (void)rc;
    return rows;
}

PYBIND11_MODULE(mapmatching4gmns_engine, m) {
    m.doc() = "Corridor2GMNS in-process binding for Zhou's MapMatching4GMNS (trace2route)";
    m.def("run_in_dir", &run_in_dir, py::arg("work_dir"),
          "Run trace2route in work_dir (node/link/trace.csv) -> list of route rows.");
    m.def("reset", &mm_reset_state, "Clear all engine global state.");
    m.attr("__version__") = "0.1.0";
    m.attr("engine") = "MapMatching4GMNS/trace2route (Zhou)";
    // whether this build can actually run the agent loop in parallel. When false, the batch
    // still works (one network load, many agents) but runs single-threaded regardless of
    // CORRIDOR2GMNS_MM_THREADS. Rebuild with MM_OPENMP=1 to get a parallel-capable module.
#ifdef _OPENMP
    m.attr("openmp") = true;
#else
    m.attr("openmp") = false;
#endif
    m.attr("threads_env") = "CORRIDOR2GMNS_MM_THREADS";
}
