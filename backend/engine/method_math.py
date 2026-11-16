"""Stable teaching registry/lookup; declarations live in math_lessons by family."""

from copy import deepcopy

from engine.math_lessons import causal, domain, evaluate, machine, modeling, prepare, series, stats
from engine.math_sources import scipy as scipy
from engine.math_sources import source as source

LESSONS = {}


def add(method_id, variant, formula, meaning, symbols, steps, conditions, example, *sources):
    if method_id in LESSONS:
        raise ValueError(f"Duplicate math lesson: {method_id}")
    LESSONS[method_id] = dict(
        variant=variant,
        formula=formula,
        meaning=meaning,
        symbols=symbols,
        steps=steps,
        conditions=conditions,
        example="教学示例（非真实实验）：" + example,
        sources=list(sources),
    )


prepare.populate(add)
stats.populate(add)
modeling.populate(add)
machine.populate(add)
series.populate(add)
causal.populate(add)
evaluate.populate(add)
domain.populate(add)


# Replace handbook landing pages with the specific supporting sections.
for _mid, _path, _section in [
    ("design.factorial", "pri/section3/pri3332", "5.3.3.3.2 Full factorial example"),
    (
        "design.orthogonal",
        "pri/section3/pri334",
        "Fractional factorial designs; orthogonality and aliasing",
    ),
    ("design.rsm", "pri/section3/pri336", "5.3.3.6 Quadratic response surface equations"),
    ("design.ccd", "pri/section3/pri3361", "5.3.3.6.1 Central composite designs and alpha"),
    (
        "design.boxbehnken",
        "pri/section3/pri3362",
        "5.3.3.6.2 Three-factor geometry; higher-dimensional pair construction is local",
    ),
    (
        "domain.control",
        "pmc/section3/pmc324",
        "6.3.2.4 EWMA statistic and asymptotic control limits",
    ),
    ("domain.capability", "pmc/section1/pmc16", "6.1.6 Cp and Cpk definitions"),
]:
    LESSONS[_mid]["sources"] = [
        source(
            "NIST/SEMATECH · " + _section,
            "https://www.itl.nist.gov/div898/handbook/" + _path + ".htm",
            _section,
        )
    ]

# Accessible primary documentation supplements publisher pages with access limits.
LESSONS["series.tobit"]["sources"].append(
    source(
        "Stata · Tobit",
        "https://www.stata.com/manuals/rtobit.pdf",
        "Methods and formulas: left/right/two-limit censored normal likelihood",
    )
)
LESSONS["causal.heckman"]["sources"].append(
    source(
        "Stata · Heckman",
        "https://www.stata.com/manuals/rheckman.pdf",
        "Methods and formulas: two-step estimator and inverse Mills ratio",
    )
)
LESSONS["causal.psm"]["sources"].append(
    source(
        "Cunningham · Unconfoundedness",
        "https://mixtape.scunning.com/05-causal_cross_sectional_designs",
        "Propensity scores, matching, overlap and ATT",
    )
)
LESSONS["causal.placebo"]["sources"].append(
    scipy(
        "permutation_test",
        "Notes: permutation types and conservative add-one convention; local code instead uses absolute tail count/B",
    )
)


def lesson(method_id):
    """Return an independent JSON-compatible lesson, including implementation provenance."""
    value = deepcopy(LESSONS.get(method_id))
    if value is None:
        return None
    prefix = method_id.split(".")[0]
    module = {
        "prep": "prepare",
        "describe": "stats",
        "test": "stats",
        "model": "modeling",
        "ml": "machine",
        "series": "series",
        "causal": "causal",
        "design": "causal",
        "eval": "evaluate",
        "domain": "domain",
    }[prefix]
    value["implementation"] = f"backend/engine/methods/{module}.py · {method_id}"
    value["version"] = 1
    return value


def public_lesson(method_id):
    value = lesson(method_id)
    if value:
        value.pop("implementation", None)
    return value
