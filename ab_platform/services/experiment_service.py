"""实验管理服务：CRUD + 状态机 + 实验组/层管理"""
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Experiment, ExperimentGroup, Layer

# 状态流转规则
VALID_TRANSITIONS = {
    "draft": ["ramp_up", "ended"],
    "ramp_up": ["running", "paused"],
    "running": ["paused", "ended"],
    "paused": ["running", "ended"],
    "ended": [],  # 终态，不可流转
}

STATUS_LABELS = {
    "draft": "草稿",
    "ramp_up": "灰度放量",
    "running": "运行中",
    "paused": "已暂停",
    "ended": "已结束",
}


def _validate_transition(current_status: str, new_status: str):
    """校验状态流转是否合法"""
    allowed = VALID_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        raise ValueError(
            f"不允许从 '{STATUS_LABELS[current_status]}' 转为 '{STATUS_LABELS[new_status]}'"
        )


def get_or_create_default_layer(session: Session) -> Layer:
    """获取或创建默认流量层"""
    layer = session.query(Layer).filter_by(name="default_layer").first()
    if not layer:
        layer = Layer(name="default_layer", total_buckets=10000, description="默认流量层")
        session.add(layer)
        session.commit()
        session.refresh(layer)
    return layer


def _generate_experiment_code(session: Session, owner: str) -> str:
    """生成实验业务编号：EXP-{owner缩写}-{YYYYMMDD}-{当日序号}"""
    today_str = date.today().strftime("%Y%m%d")
    owner_abbr = owner[:4] if len(owner) >= 2 else owner
    # 查询今天该 owner 已创建的数量
    count_today = (
        session.query(func.count(Experiment.id))
        .filter(
            Experiment.owner == owner,
            func.date(Experiment.created_at) == date.today(),
        )
        .scalar() or 0
    )
    seq = str(count_today + 1).zfill(3)
    return f"EXP-{owner_abbr}-{today_str}-{seq}"


def create_experiment(
    session: Session,
    name: str,
    hypothesis: str,
    owner: str,
    total_traffic_pct: float = 10.0,
    group_configs: list = None,
) -> Experiment:
    """创建实验及其分组"""
    layer = get_or_create_default_layer(session)
    exp_code = _generate_experiment_code(session, owner)

    exp = Experiment(
        experiment_code=exp_code,
        name=name,
        hypothesis=hypothesis,
        owner=owner,
        total_traffic_pct=total_traffic_pct,
        layer_id=layer.id,
        status="draft",
    )
    session.add(exp)
    session.flush()

    if group_configs is None:
        group_configs = [
            {"group_name": "对照组", "traffic_pct": 50.0},
            {"group_name": "实验组", "traffic_pct": 50.0},
        ]

    _assign_buckets(session, exp, group_configs)
    session.commit()
    session.refresh(exp)
    return exp


def _assign_buckets(session: Session, exp: Experiment, group_configs: list):
    """为实验组分配桶区间"""
    total_buckets = 10000
    exp_bucket_count = int(total_buckets * exp.total_traffic_pct / 100)

    # 查找层内已占用的桶区间
    existing_exps = (
        session.query(Experiment)
        .filter(
            Experiment.layer_id == exp.layer_id,
            Experiment.status.in_(["ramp_up", "running", "paused"]),
            Experiment.id != exp.id,
        )
        .all()
    )
    used_ranges = []
    for e in existing_exps:
        for g in e.groups:
            used_ranges.append((g.bucket_range_start, g.bucket_range_end))

    # 找到第一个可用的连续区间
    start = 0
    for used_start, used_end in sorted(used_ranges):
        if start + exp_bucket_count <= used_start:
            break
        start = max(start, used_end)
    if start + exp_bucket_count > total_buckets:
        raise ValueError(f"层内桶空间不足，需要 {exp_bucket_count} 个桶，仅剩 {total_buckets - start} 个")

    # 按比例分配桶给各组
    cursor = start
    for cfg in group_configs:
        group_buckets = int(exp_bucket_count * cfg["traffic_pct"] / 100)
        grp = ExperimentGroup(
            experiment_id=exp.id,
            group_name=cfg["group_name"],
            bucket_range_start=cursor,
            bucket_range_end=cursor + group_buckets,
            traffic_pct=cfg["traffic_pct"],
        )
        session.add(grp)
        cursor += group_buckets


def update_experiment_status(session: Session, exp_id: int, new_status: str):
    """更新实验状态，带流转校验"""
    exp = session.query(Experiment).filter_by(id=exp_id).first()
    if not exp:
        raise ValueError("实验不存在")
    _validate_transition(exp.status, new_status)

    if new_status == "running" and exp.start_date is None:
        exp.start_date = date.today()
    if new_status == "ended":
        exp.end_date = date.today()

    exp.status = new_status
    exp.updated_at = date.today()
    session.commit()
    return exp


def get_experiment(session: Session, exp_id: int) -> Experiment:
    return session.query(Experiment).filter_by(id=exp_id).first()


def list_experiments(session: Session) -> list:
    return session.query(Experiment).order_by(Experiment.created_at.desc()).all()


def delete_experiment(session: Session, exp_id: int):
    exp = session.query(Experiment).filter_by(id=exp_id).first()
    if exp and exp.status == "draft":
        session.delete(exp)
        session.commit()
        return True
    return False


def update_experiment_traffic(session: Session, exp_id: int, new_traffic_pct: float):
    """更新实验流量比例（渐进放量），重新分配桶区间"""
    exp = session.query(Experiment).filter_by(id=exp_id).first()
    if not exp:
        raise ValueError("实验不存在")
    # 先保存旧配置再删除
    old_configs = [{"group_name": g.group_name, "traffic_pct": g.traffic_pct} for g in exp.groups]
    for g in exp.groups:
        session.delete(g)
    session.flush()
    # 按原有组比例重新分配
    exp.total_traffic_pct = new_traffic_pct
    _assign_buckets(session, exp, old_configs)
    session.commit()
    session.refresh(exp)
    return exp
