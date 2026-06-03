"""统计计算辅助函数"""
import numpy as np
from scipy import stats
from typing import Optional, Tuple


def welch_ttest(mean1: float, std1: float, n1: int,
                mean2: float, std2: float, n2: int) -> dict:
    """Welch's t检验（不假设方差齐性）"""
    if n1 < 2 or n2 < 2:
        return {"t_stat": None, "p_value": None, "ci_lower": None, "ci_upper": None,
                "error": "样本量不足"}

    se = np.sqrt(std1**2 / n1 + std2**2 / n2)
    t_stat = (mean2 - mean1) / se if se > 0 else 0
    # Welch-Satterthwaite 自由度
    df_num = (std1**2 / n1 + std2**2 / n2)**2
    df_den = ((std1**2 / n1)**2 / (n1 - 1) + (std2**2 / n2)**2 / (n2 - 1))
    df = df_num / df_den if df_den > 0 else 1
    p_value = 2 * stats.t.sf(abs(t_stat), df)
    # 95% CI for the difference
    t_crit = stats.t.ppf(0.975, df)
    diff = mean2 - mean1
    ci_lower = diff - t_crit * se
    ci_upper = diff + t_crit * se
    return {"t_stat": t_stat, "p_value": p_value, "ci_lower": ci_lower, "ci_upper": ci_upper}


def ztest_proportion(p1: float, n1: int, p2: float, n2: int) -> dict:
    """两样本比例 z 检验"""
    if n1 < 5 or n2 < 5:
        return {"z_stat": None, "p_value": None, "ci_lower": None, "ci_upper": None,
                "error": "样本量不足"}

    p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
    se = np.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    z_stat = (p2 - p1) / se if se > 0 else 0
    p_value = 2 * stats.norm.sf(abs(z_stat))
    # 95% CI for difference in proportions
    se_diff = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    diff = p2 - p1
    ci_lower = diff - 1.96 * se_diff
    ci_upper = diff + 1.96 * se_diff
    return {"z_stat": z_stat, "p_value": p_value, "ci_lower": ci_lower, "ci_upper": ci_upper}


def calc_lift(control_mean: float, treatment_mean: float) -> Optional[float]:
    """计算相对提升 (%)"""
    if control_mean is None or control_mean == 0:
        return None
    return (treatment_mean - control_mean) / control_mean * 100


def calc_sample_size(effect_size: float, std: float = 1.0,
                     alpha: float = 0.05, power: float = 0.8) -> int:
    """估算每组所需最小样本量（两样本双侧 t 检验）"""
    from statsmodels.stats.power import TTestIndPower
    analysis = TTestIndPower()
    n = analysis.solve_power(
        effect_size=effect_size / std,
        alpha=alpha,
        power=power,
        alternative="two-sided",
    )
    return int(np.ceil(n))


def summarize_result(control_mean: float, treatment_mean: float,
                     n1: int, n2: int, std1: float = None, std2: float = None,
                     metric_type: str = "continuous", control_std: float = None,
                     treatment_std: float = None) -> dict:
    """对单个指标完成统计检验并汇总结果"""
    result = {
        "control_mean": control_mean,
        "treatment_mean": treatment_mean,
        "control_n": n1,
        "treatment_n": n2,
        "control_std": control_std,
        "treatment_std": treatment_std,
        "p_value": None,
        "ci_lower": None,
        "ci_upper": None,
        "is_significant": False,
        "lift_pct": None,
        "method": metric_type,
    }

    if metric_type == "proportion":
        test_result = ztest_proportion(control_mean, n1, treatment_mean, n2)
        result["method"] = "z-test"
    else:
        if std1 is None or std2 is None:
            result["error"] = "缺少标准差"
            return result
        test_result = welch_ttest(control_mean, std1, n1, treatment_mean, std2, n2)
        result["method"] = "Welch's t-test"

    if "error" in test_result:
        result["error"] = test_result["error"]
        return result

    result["p_value"] = test_result["p_value"]
    ci_low, ci_up = test_result["ci_lower"], test_result["ci_upper"]
    result["ci_lower"] = ci_low
    result["ci_upper"] = ci_up
    result["is_significant"] = (test_result["p_value"] is not None and test_result["p_value"] < 0.05)

    # lift: 将差值的 CI 转换为相对提升的 CI
    if control_mean and control_mean != 0:
        result["lift_pct"] = (treatment_mean - control_mean) / control_mean * 100
        if ci_low is not None:
            result["ci_lower_pct"] = ci_low / control_mean * 100
        if ci_up is not None:
            result["ci_upper_pct"] = ci_up / control_mean * 100

    return result
