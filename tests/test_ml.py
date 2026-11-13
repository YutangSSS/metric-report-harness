import pytest

pytest.importorskip("sklearn")


def test_recurrence_split_censoring_and_bar(con):
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "ml"))
    from recurrence import WINDOW_DAYS, build_rows, fit_and_score
    from datetime import timedelta

    data, cut = build_rows(con)
    assert all(d + timedelta(days=WINDOW_DAYS) <= cut for d in data["outcome_dt"])  # every label fully observed
    results, meta, _ = fit_and_score(con)
    assert meta["train_last_outcome"] < meta["test_first_outcome"]  # time split, no overlap
    base = results["base rate (train)"]["brier"]
    for name in ("logistic regression", "gradient boosting"):
        assert results[name]["auc"] > 0.6
        assert results[name]["brier"] < base  # must beat predicting the average
