
//          Copyright Sebastian Jeckel 2014.
// Distributed under the Boost Software License, Version 1.0.
//    (See accompanying file LICENSE_1_0.txt or copy at
//          http://www.boost.org/LICENSE_1_0.txt)

#pragma once

#include "gtest/gtest.h"

#include <vector>

#include "react/Domain.h"
#include "react/Signal.h"
#include "react/Event.h"
#include "react/Observer.h"

///////////////////////////////////////////////////////////////////////////////////////////////////
namespace {

using namespace react;

///////////////////////////////////////////////////////////////////////////////////////////////////
/// LazyTest fixture
///////////////////////////////////////////////////////////////////////////////////////////////////
template <typename TParams>
class LazyTest : public testing::Test
{
public:
    template <EPropagationMode mode>
    class MyEngine : public TParams::template EngineT<mode> {};

    REACTIVE_DOMAIN(MyDomain, TParams::mode, MyEngine)
};

TYPED_TEST_CASE_P(LazyTest);

///////////////////////////////////////////////////////////////////////////////////////////////////
/// Detach test
///////////////////////////////////////////////////////////////////////////////////////////////////
TYPED_TEST_P(LazyTest, Lazy)
{
    using D = typename Lazy::MyDomain;

    auto a1 = MakeEventSource<D, int>();

    int observeCount1 = 0;
    int observeCount2 = 0;
    int transformCount = 0;

    int phase;

    auto obs1 = Observe<D>(a1, [&] (int v)
    {
        observeCount1++;

        if (phase == 0)
            ASSERT_EQ(v,2);
        else if (phase == 1)
            ASSERT_EQ(v,3);
        else if (phase == 2)
            ASSERT_EQ(v,4);
    });

    auto trans1 = Transform(a1, [&] (const int v)
    {
        transformCount++;
        return 42;
    });



    phase = 0;
    a1 << 2;
    ASSERT_EQ(observeCount1,1);
    ASSERT_EQ(transformCount,0);

    phase = 1;
    auto obs2 = Observe(trans1, [&] (int v)
    {
        observeCount2++;
        if (phase == 1)
            ASSERT_EQ(v,42);
        else
            ASSERT_TRUE(false);
    });
    a1 << 3;
    ASSERT_EQ(observeCount1,2);
    ASSERT_EQ(observeCount2,1);
    ASSERT_EQ(transformCount,1);

    phase = 2;
    obs2.Detach();
    a1 << 4;
    ASSERT_EQ(observeCount1,3);
    ASSERT_EQ(observeCount2,1);
    ASSERT_EQ(transformCount,1);
}


///////////////////////////////////////////////////////////////////////////////////////////////////
REGISTER_TYPED_TEST_CASE_P
(
    LazyTest,
    Lazy
);

} // ~namespace
