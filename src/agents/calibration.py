"""Calibration metrics for evaluating the rubric judge against human labels."""
from __future__ import annotations


def confusion_counts(
    y_true: list[bool], y_pred: list[bool]
) -> tuple[int, int, int, int]:
    """Return (true_positives, false_positives, false_negatives, true_negatives)."""
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must be the same length")
    tp = fp = fn = tn = 0
    for actual, predicted in zip(y_true, y_pred):
        if predicted and actual:
            tp += 1
        elif predicted and not actual:
            fp += 1
        elif not predicted and actual:
            fn += 1
        else:
            tn += 1
    return tp, fp, fn, tn


def precision_recall(
    y_true: list[bool], y_pred: list[bool]
) -> tuple[float, float]:
    """Precision and recall of the 'passed' class."""
    tp, fp, fn, _ = confusion_counts(y_true, y_pred)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return precision, recall


def cohen_kappa(y_true: list[bool], y_pred: list[bool]) -> float:
    """Cohen's kappa for binary labels (1.0 perfect, 0.0 chance-level)."""
    tp, fp, fn, tn = confusion_counts(y_true, y_pred)
    total = tp + fp + fn + tn
    if total == 0:
        return 0.0
    observed = (tp + tn) / total
    p_pass = ((tp + fp) / total) * ((tp + fn) / total)
    p_fail = ((fp + tn) / total) * ((fn + tn) / total)
    expected = p_pass + p_fail
    if expected == 1.0:
        return 0.0
    return (observed - expected) / (1.0 - expected)
