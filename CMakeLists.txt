### Configuration
cmake_minimum_required (VERSION 2.6)
enable_testing()

project (CppReact)
find_package(TBB REQUIRED tbb)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set (CMAKE_CXX_STANDARD 14)
if (NOT WIN32)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++14 -Wall -Wpedantic")
endif ()

include_directories (SYSTEM "${PROJECT_SOURCE_DIR}/include")
#TODO send diff
include_directories("${TBB_DIR}/../include")
### CppReact
file(GLOB_RECURSE CPPREACT_HEADERS include/*.h)

add_library(CppReact 
	src/engine/PulsecountEngine.cpp
	src/engine/SubtreeEngine.cpp
	src/engine/ToposortEngine.cpp
	src/logging/EventLog.cpp
        src/logging/EventRecords.cpp
        ${CPPREACT_HEADERS})

target_link_libraries(CppReact "${TBB_DIR}/../lib/intel64/vc14/tbb_debug.lib")
### examples/ 
option(build_examples "Build examples?" ON)
if(build_examples)
	add_subdirectory(examples)
endif()

### benchmarks/ 
option(build_benchmarks "Build benchmarks?" ON)
if(build_benchmarks)
	add_subdirectory(benchmarks)
endif()

### tests/ 
option(build_tests "Build unit tests?" ON)
if(build_tests)
	add_subdirectory(tests)
endif()
