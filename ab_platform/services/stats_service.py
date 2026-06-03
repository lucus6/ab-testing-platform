"""统计引擎：假设检验 + 置信区间 + 样本量估算"""
import pandas as pd
from sqlalchemy.orm import Session
from models import MetricDefinition
from services.metrics_service import compute_metric_summary, get_all_metrics, init_default_metrics
from utils.stats_utils import summarize_result


def analyze_experiment(session: Session, experiment_id: int) -> list:
    """对实验的所有指标做显著性检验"""
    init_default_metrics(session)
    metrics = get_all_metrics(session)
    results = []

    for metric in metrics:
        summary = compute_metric_summary(session, experiment_id, metric)
        groups = summary["groups"]
        if len(groups) < 2:
            continue

        group_names = list(groups.keys())
        # 找对照组和实验组
        control_key = None
        treat_keys = []
        for name in group_names:
            if "对照" in name:
                control_key = name
            elif "实验" in name:
                treat_keys.append(name)
        if control_key is None:
            control_key = group_names[0]
        if not treat_keys:
            treat_keys = [n for n in group_names if n != control_key]

        ctrl = groups[control_key]
        for tk in treat_keys:
            treat = groups[tk]
            result = summarize_result(
                control_mean=ctrl["mean"],
                treatment_mean=treat["mean"],
                n1=ctrl["n"],
                n2=treat["n"],
                std1=ctrl.get("std"),
                std2=treat.get("std"),
                control_std=ctrl.get("std"),
                treatment_std=treat.get("std"),
                metric_type=summary["metric_type"],
            )
            result["metric_name"] = metric.name
            result["category"] = metric.category
            result["control_name"] = control_key
            result["treatment_name"] = tk
            results.append(result)

    return results


def get_significance_summary(results: list) -> dict:
    """汇总显著性结果"""
    total = len(results)
    sig = sum(1 for r in results if r.get("is_significant"))
    north_star_sig = sum(
        1 for r in results
        if r.get("is_significant") and r.get("category") == "north_star"
    )
    return {
        "total_metrics": total,
        "significant_metrics": sig,
        "significant_north_star": north_star_sig,
        "has_positive_signal": sig > 0,
    }
