import pytest

from src.agents.calibration import cohen_kappa, confusion_counts, precision_recall


def test_confusion_counts_mixed():
    y_true = [True, False, True, False, True]
    y_pred = [True, False, False, True, True]
    assert confusion_counts(y_true, y_pred) == (2, 1, 1, 1)


def test_confusion_counts_length_mismatch():
    with pytest.raises(ValueError):
        confusion_counts([True], [])


def test_precision_recall_perfect():
    assert precision_recall([True, False, True], [True, False, True]) == (1.0, 1.0)


def test_precision_recall_partial():
    y_true = [True, True, False, False]
    y_pred = [True, False, True, False]
    precision, recall = precision_recall(y_true, y_pred)
    assert precision == pytest.approx(0.5)
    assert recall == pytest.approx(0.5)


def test_precision_zero_when_no_positive_predictions():
    assert precision_recall([True, False], [False, False]) == (0.0, 0.0)


def test_cohen_kappa_perfect():
    assert cohen_kappa([True, False, True], [True, False, True]) == pytest.approx(1.0)


def test_cohen_kappa_negative_for_inverted():
    y_true = [True, False, True, False]
    y_pred = [False, True, False, True]
    assert cohen_kappa(y_true, y_pred) == pytest.approx(-1.0)


def test_cohen_kappa_constant_agreement_returns_zero():
    assert cohen_kappa([True, True], [True, True]) == 0.0
