# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from specweaver.core.flow.engine.models import RouterDefinition, RouterRule, RuleOperator
from specweaver.core.flow.engine.routers import RouterEvaluator


def test_router_evaluator_eq():
    router = RouterDefinition(
        rules=[
            RouterRule(
                field="status", operator=RuleOperator.EQ, value="complex", target="decompose"
            ),
        ],
        default_target="fast_track",
    )
    evaluator = RouterEvaluator()

    assert evaluator.evaluate(router, {"status": "complex"}) == "decompose"
    assert evaluator.evaluate(router, {"status": "simple"}) == "fast_track"
    assert evaluator.evaluate(router, {}) == "fast_track"


def test_router_evaluator_nested_field():
    router = RouterDefinition(
        rules=[
            RouterRule(
                field="metrics.score", operator=RuleOperator.GT, value=90, target="auto_approve"
            ),
        ],
        default_target="manual_review",
    )
    evaluator = RouterEvaluator()

    assert evaluator.evaluate(router, {"metrics": {"score": 95}}) == "auto_approve"
    assert evaluator.evaluate(router, {"metrics": {"score": 80}}) == "manual_review"
    assert evaluator.evaluate(router, {"metrics": {}}) == "manual_review"
    assert evaluator.evaluate(router, {}) == "manual_review"


def test_router_evaluator_all_operators():
    evaluator = RouterEvaluator()

    # NEQ
    rule = RouterRule(field="count", operator=RuleOperator.NEQ, value=0, target="hit")
    assert (
        evaluator.evaluate(RouterDefinition(rules=[rule], default_target="miss"), {"count": 1})
        == "hit"
    )
    assert (
        evaluator.evaluate(RouterDefinition(rules=[rule], default_target="miss"), {"count": 0})
        == "miss"
    )

    # LT
    rule = RouterRule(field="count", operator=RuleOperator.LT, value=5, target="hit")
    assert (
        evaluator.evaluate(RouterDefinition(rules=[rule], default_target="miss"), {"count": 4})
        == "hit"
    )
    assert (
        evaluator.evaluate(RouterDefinition(rules=[rule], default_target="miss"), {"count": 5})
        == "miss"
    )

    # CONTAINS
    rule = RouterRule(field="tags", operator=RuleOperator.CONTAINS, value="urgent", target="hit")
    assert (
        evaluator.evaluate(
            RouterDefinition(rules=[rule], default_target="miss"), {"tags": ["bug", "urgent"]}
        )
        == "hit"
    )
    assert (
        evaluator.evaluate(RouterDefinition(rules=[rule], default_target="miss"), {"tags": ["bug"]})
        == "miss"
    )

    # IN
    rule = RouterRule(field="category", operator=RuleOperator.IN, value=["A", "B"], target="hit")
    assert (
        evaluator.evaluate(RouterDefinition(rules=[rule], default_target="miss"), {"category": "B"})
        == "hit"
    )
    assert (
        evaluator.evaluate(RouterDefinition(rules=[rule], default_target="miss"), {"category": "C"})
        == "miss"
    )

    # IS_EMPTY
    rule = RouterRule(field="errors", operator=RuleOperator.IS_EMPTY, target="hit")
    assert (
        evaluator.evaluate(RouterDefinition(rules=[rule], default_target="miss"), {"errors": []})
        == "hit"
    )
    assert (
        evaluator.evaluate(
            RouterDefinition(rules=[rule], default_target="miss"), {"errors": ["e1"]}
        )
        == "miss"
    )
    # missing field is considered empty? Yes, probably safely.
    assert evaluator.evaluate(RouterDefinition(rules=[rule], default_target="miss"), {}) == "hit"

    # NOT_EMPTY
    rule = RouterRule(field="errors", operator=RuleOperator.NOT_EMPTY, target="hit")
    assert (
        evaluator.evaluate(
            RouterDefinition(rules=[rule], default_target="miss"), {"errors": ["e1"]}
        )
        == "hit"
    )
    assert (
        evaluator.evaluate(RouterDefinition(rules=[rule], default_target="miss"), {"errors": []})
        == "miss"
    )
    assert evaluator.evaluate(RouterDefinition(rules=[rule], default_target="miss"), {}) == "miss"
