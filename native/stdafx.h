// Portable shim replacing MFC stdafx.h -- cross-platform (Windows / macOS / Linux).
#pragma once
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cassert>
#include <iostream>
#include <algorithm>
#include <type_traits>

// MFC debug macros -> portable
#ifndef TRACE
#define TRACE(...) ((void)0)
#endif
#ifndef ASSERT
#define ASSERT(x) assert(x)
#endif

// MSVC's std::max/min accept mixed arithmetic types; standard C++ (g++/clang) does not.
// Provide mixed-type overloads, SFINAE-disabled for same-type so std::max/min still win there.
template <class A, class B,
          typename std::enable_if<!std::is_same<A, B>::value, int>::type = 0>
typename std::common_type<A, B>::type max(A a, B b) { return a > b ? a : b; }
template <class A, class B,
          typename std::enable_if<!std::is_same<A, B>::value, int>::type = 0>
typename std::common_type<A, B>::type min(A a, B b) { return a < b ? a : b; }
