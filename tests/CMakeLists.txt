find_package(GTest REQUIRED)
find_package(Threads REQUIRED)

function(cppreact_test)
    set(options SKIPPED BOOST BENCHMARK)
    set(oneValueArgs NAME)
    set(multiValueArgs SOURCES)
    cmake_parse_arguments(cppreact_test "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN})

    add_executable (${cppreact_test_NAME} ${cppreact_test_SOURCES})
    target_link_libraries(${cppreact_test_NAME} CppReact ${GTEST_BOTH_LIBRARIES} ${CMAKE_THREAD_LIBS_INIT})

    # GTEST_ADD_TESTS does not seem to be able to find our tests ...
    # pure guess : because of INSTANTIATE_TYPED_TEST_CASE_P usage ?
    #GTEST_ADD_TESTS(${cppreact_test_NAME} "" AUTO)
    add_test(NAME ${cppreact_test_NAME} COMMAND ${cppreact_test_NAME})
endfunction(cppreact_test)

cppreact_test(NAME EventStreamTest  SOURCES src/EventStreamTest.cpp)
cppreact_test(NAME EventStreamTestQ SOURCES src/EventStreamTestQ.cpp)
cppreact_test(NAME MoveTest         SOURCES src/MoveTest.cpp)
cppreact_test(NAME ObserverTest     SOURCES src/ObserverTest.cpp)
cppreact_test(NAME ObserverTestQ    SOURCES src/ObserverTestQ.cpp)
cppreact_test(NAME OperationsTest   SOURCES src/OperationsTest.cpp)
cppreact_test(NAME OperationsTestQ  SOURCES src/OperationsTestQ.cpp)
cppreact_test(NAME SignalTest       SOURCES src/SignalTest.cpp)
cppreact_test(NAME SignalTestQ      SOURCES src/SignalTestQ.cpp)
cppreact_test(NAME TransactionTest  SOURCES src/TransactionTest.cpp)
cppreact_test(NAME LazyTest         SOURCES src/LazyTest.cpp)
