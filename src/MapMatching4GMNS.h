
#include <iostream>

#ifndef GUARD_MAPMATCHING4GMNS_ENGINE_H

#ifdef _WIN32
#define MAPMATCHING4GMNS_ENGINE_API __declspec(dllexport)
#else
#define MAPMATCHING4GMNS_ENGINE_API
#endif

extern "C" MAPMATCHING4GMNS_ENGINE_API void MapMatching4GMNS(const int mode);

#endif