
//          Copyright Sebastian Jeckel 2014.
// Distributed under the Boost Software License, Version 1.0.
//    (See accompanying file LICENSE_1_0.txt or copy at
//          http://www.boost.org/LICENSE_1_0.txt)

#pragma once

#include "react/detail/Defs.h"

#include <atomic>
#include <functional>
#include <limits>
#include <memory>
#include <mutex>
#include <utility>

#include "tbb/concurrent_vector.h"

#include "react/detail/IReactiveNode.h."

/***************************************/ REACT_IMPL_BEGIN /**************************************/

using TurnIdT = uint;
using TurnFlagsT = uint;

///////////////////////////////////////////////////////////////////////////////////////////////////
/// ContinuationInput
///////////////////////////////////////////////////////////////////////////////////////////////////
class ContinuationInput
{
public:
    using InputClosureT = std::function<void()>;
    using InputVectT    = tbb::concurrent_vector<InputClosureT>;
    
    inline ContinuationInput& operator=(ContinuationInput&& other)
    {
        bufferedInputsPtr_ = std::move(other.bufferedInputsPtr_);
        return *this;
    }

    inline bool IsEmpty() const { return bufferedInputsPtr_ == nullptr; }

    template <typename F>
    void Add(F&& input)
    {
        std::call_once(bufferedInputsInit_, [this] {
            bufferedInputsPtr_.reset(new InputVectT());
        });
        bufferedInputsPtr_->push_back(std::forward<F>(input));
    }

    inline void Execute()
    {
        if (bufferedInputsPtr_ != nullptr)
        {
            for (auto f : *bufferedInputsPtr_)
                f();
            bufferedInputsPtr_->clear();
        }
    }

private:
    std::once_flag                  bufferedInputsInit_;
    std::unique_ptr<InputVectT>     bufferedInputsPtr_ = nullptr;
};

///////////////////////////////////////////////////////////////////////////////////////////////////
/// ContinuationHolder
///////////////////////////////////////////////////////////////////////////////////////////////////
template <typename D>
class ContinuationHolder
{
public:
    using TurnT = typename D::TurnT;

    ContinuationHolder() = delete;

    static void                 SetTurn(TurnT& turn)    { ptr_ = &turn.continuation_; }
    static void                 Clear()                 { ptr_ = nullptr; }
    static ContinuationInput*   Get()                   { return ptr_; }

private:
    static REACT_TLS ContinuationInput* ptr_;
};

template <typename D>
ContinuationInput* ContinuationHolder<D>::ptr_(nullptr);

///////////////////////////////////////////////////////////////////////////////////////////////////
/// InputManager
///////////////////////////////////////////////////////////////////////////////////////////////////
template <typename D>
class InputManager
{
public:
    using TurnT = typename D::TurnT;
    using Engine = typename D::Engine;

    template <typename F>
    static void DoTransaction(TurnFlagsT flags, F&& func)
    {
        // Attempt to add input to another turn.
        // If successful, blocks until other turn is done and returns.
        if (Engine::TryMerge(std::forward<F>(func)))
            return;

        bool shouldPropagate = false;

        auto turn = makeTurn(flags);

        // Phase 1 - Input admission
        transactionState_.Active = true;
        Engine::OnTurnAdmissionStart(turn);
        func();
        Engine::OnTurnAdmissionEnd(turn);
        transactionState_.Active = false;

        // Phase 2 - Apply input node changes
        for (auto* p : transactionState_.Inputs)
            if (p->ApplyInput(&turn))
                shouldPropagate = true;
        transactionState_.Inputs.clear();

        // Phase 3 - Propagate changes
        if (shouldPropagate)
            Engine::OnTurnPropagate(turn);

        Engine::OnTurnEnd(turn);

        postProcessTurn(turn);
    }

    template <typename R, typename V>
    static void AddInput(R&& r, V&& v)
    {
        if (ContinuationHolder<D>::Get() != nullptr)
        {
            addContinuationInput(std::forward<R>(r), std::forward<V>(v));
        }
        else if (transactionState_.Active)
        {
            addTransactionInput(std::forward<R>(r), std::forward<V>(v));
        }
        else
        {
            addSimpleInput(std::forward<R>(r), std::forward<V>(v));
        }
    }

private:
    static std::atomic<TurnIdT> nextTurnId_;

    static TurnIdT nextTurnId()
    {
        auto curId = nextTurnId_.fetch_add(1, std::memory_order_relaxed);

        if (curId == (std::numeric_limits<int>::max)())
            nextTurnId_.fetch_sub((std::numeric_limits<int>::max)());

        return curId;
    }

    struct TransactionState
    {
        bool    Active = false;
        std::vector<IInputNode*>    Inputs;
    };

    static TransactionState transactionState_;

    static TurnT makeTurn(TurnFlagsT flags)
    {
        return TurnT(nextTurnId(), flags);
    }

    // Create a turn with a single input
    template <typename R, typename V>
    static void addSimpleInput(R&& r, V&& v)
    {
        auto turn = makeTurn(0);

        Engine::OnTurnAdmissionStart(turn);
        r.AddInput(std::forward<V>(v));
        Engine::OnTurnAdmissionEnd(turn);

        if (r.ApplyInput(&turn))
            Engine::OnTurnPropagate(turn);

        Engine::OnTurnEnd(turn);

        postProcessTurn(turn);
    }

    // This input is part of an active transaction
    template <typename R, typename V>
    static void addTransactionInput(R&& r, V&& v)
    {
        r.AddInput(std::forward<V>(v));
        transactionState_.Inputs.push_back(&r);
    }

    // Input happened during a turn - buffer in continuation
    template <typename R, typename V>
    static void addContinuationInput(R&& r, V&& v)
    {
        // Copy v
        ContinuationHolder<D>::Get()->Add(
            [&r,v] { addTransactionInput(r, std::move(v)); }
        );
    }

    static void postProcessTurn(TurnT& turn)
    {
        turn.detachObservers<D>();

        // Steal continuation from current turn
        if (! turn.continuation_.IsEmpty())
            processContinuations(std::move(turn.continuation_), 0);
    }

    static void processContinuations(ContinuationInput&& cont, TurnFlagsT flags)
    {
        // No merging for continuations
        flags &= ~enable_input_merging;

        while (true)
        {
            bool shouldPropagate = false;
            auto turn = makeTurn(flags);

            transactionState_.Active = true;
            Engine::OnTurnAdmissionStart(turn);
            cont.Execute();
            Engine::OnTurnAdmissionEnd(turn);
            transactionState_.Active = false;

            for (auto* p : transactionState_.Inputs)
                if (p->ApplyInput(&turn))
                    shouldPropagate = true;
            transactionState_.Inputs.clear();

            if (shouldPropagate)
                Engine::OnTurnPropagate(turn);

            Engine::OnTurnEnd(turn);

            turn.detachObservers<D>();

            if (turn.continuation_.IsEmpty())
                break;

            cont = std::move(turn.continuation_);
        }
    }
};

template <typename D>
std::atomic<TurnIdT> InputManager<D>::nextTurnId_( 0 );

template <typename D>
typename InputManager<D>::TransactionState InputManager<D>::transactionState_;

/****************************************/ REACT_IMPL_END /***************************************/