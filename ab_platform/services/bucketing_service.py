"""分流引擎：哈希分桶 + 层管理 + 渐进放量"""
import hashlib
from typing import Optional
from models import Experiment, ExperimentGroup, Layer


def _hash_user(user_id: str, salt: str, total_buckets: int = 10000) -> int:
    """用 MD5 哈希将用户映射到桶编号 [0, total_buckets-1]"""
    h = hashlib.md5(f"{user_id}{salt}".encode("utf-8")).hexdigest()
    return int(h, 16) % total_buckets


def get_user_group(user_id: str, experiment: Experiment, salt: str = "") -> Optional[ExperimentGroup]:
    """
    判断用户属于实验的哪个组。
    返回 None 表示用户不在实验流量内。
    """
    if not salt:
        salt = f"exp_{experiment.id}_layer_{experiment.layer_id}"
    bucket = _hash_user(user_id, salt)

    for group in experiment.groups:
        if group.bucket_range_start <= bucket < group.bucket_range_end:
            return group
    return None


def assign_user(user_id: str, experiment: Experiment) -> dict:
    """返回用户的分组信息"""
    group = get_user_group(user_id, experiment)
    if group is None:
        return {"in_experiment": False, "group_id": None, "group_name": None}
    return {
        "in_experiment": True,
        "group_id": group.id,
        "group_name": group.group_name,
    }


def verify_bucket_consistency(user_id: str, experiment: Experiment, trials: int = 100) -> bool:
    """验证分桶一致性：同一用户多次分配结果相同"""
    first = assign_user(user_id, experiment)
    for _ in range(trials):
        if assign_user(user_id, experiment) != first:
            return False
    return True


def get_bucket_distribution(experiment: Experiment) -> dict:
    """获取实验的桶区间分布信息"""
    groups_info = []
    for g in experiment.groups:
        groups_info.append({
            "name": g.group_name,
            "start": g.bucket_range_start,
            "end": g.bucket_range_end,
            "size": g.bucket_range_end - g.bucket_range_start,
            "traffic_pct": g.traffic_pct,
        })
    return {
        "experiment_name": experiment.name,
        "total_traffic_pct": experiment.total_traffic_pct,
        "groups": groups_info,
    }
