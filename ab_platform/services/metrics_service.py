"""指标引擎：指标定义 + 聚合计算"""
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import MetricDefinition, EventLog, ExperimentGroup


# 预定义的默认指标
DEFAULT_METRICS = [
    {
        "name": "人均页面浏览数",
        "metric_type": "continuous",
        "numerator_field": "page_view",
        "denominator_field": "exposure",
        "category": "driver",
        "description": "每用户平均浏览页面数",
    },
    {
        "name": "点击率",
        "metric_type": "proportion",
        "numerator_field": "click",
        "denominator_field": "exposure",
        "category": "north_star",
        "description": "点击用户数 / 曝光用户数",
    },
    {
        "name": "购买转化率",
        "metric_type": "proportion",
        "numerator_field": "purchase",
        "denominator_field": "exposure",
        "category": "north_star",
        "description": "购买用户数 / 曝光用户数",
    },
    {
        "name": "人均购买金额",
        "metric_type": "continuous",
        "numerator_field": "purchase",
        "denominator_field": None,
        "category": "driver",
        "description": "所有曝光用户的人均购买金额",
    },
]


def init_default_metrics(session: Session):
    """初始化默认指标体系"""
    for m in DEFAULT_METRICS:
        existing = session.query(MetricDefinition).filter_by(name=m["name"]).first()
        if not existing:
            session.add(MetricDefinition(**m))
    session.commit()


def get_all_metrics(session: Session) -> list:
    return session.query(MetricDefinition).all()


def compute_metric_summary(session: Session, experiment_id: int,
                           metric_def: MetricDefinition) -> dict:
    """计算单个指标在各组的表现 (按天聚合后再汇总)"""
    # 查询各组的事件数据
    groups = session.query(ExperimentGroup).filter_by(experiment_id=experiment_id).all()
    group_results = {}

    for g in groups:
        # 分母用户数（去重）
        if metric_def.denominator_field:
            denom_users = (
                session.query(func.count(func.distinct(EventLog.user_id)))
                .filter(
                    EventLog.experiment_id == experiment_id,
                    EventLog.group_id == g.id,
                    EventLog.event_type == metric_def.denominator_field,
                )
                .scalar() or 0
            )
        else:
            denom_users = (
                session.query(func.count(func.distinct(EventLog.user_id)))
                .filter(
                    EventLog.experiment_id == experiment_id,
                    EventLog.group_id == g.id,
                )
                .scalar() or 0
            )

        if metric_def.metric_type == "continuous":
            # 连续型：按用户聚合后计算 mean/std
            #   page_view → COUNT 每用户事件数
            #   purchase  → SUM 每用户 event_value
            if "page_view" in (metric_def.numerator_field or ""):
                agg_col = func.count(EventLog.id).label("user_val")
            else:
                agg_col = func.sum(EventLog.event_value).label("user_val")

            rows = (
                session.query(EventLog.user_id, agg_col)
                .filter(
                    EventLog.experiment_id == experiment_id,
                    EventLog.group_id == g.id,
                    EventLog.event_type == metric_def.numerator_field,
                )
                .group_by(EventLog.user_id)
                .all()
            )
            user_vals = [r.user_val for r in rows if r.user_val is not None]
            overall_mean = float(np.mean(user_vals)) if user_vals else 0.0
            overall_std = float(np.std(user_vals, ddof=1)) if len(user_vals) >= 2 else 0.0
            n_unique_users = len(user_vals)

            group_results[g.group_name] = {
                "mean": overall_mean,
                "std": overall_std,
                "n": n_unique_users,
            }

        elif metric_def.metric_type == "proportion":
            # 比率型：发生事件的用户数 / 分母用户数
            num_users = (
                session.query(func.count(func.distinct(EventLog.user_id)))
                .filter(
                    EventLog.experiment_id == experiment_id,
                    EventLog.group_id == g.id,
                    EventLog.event_type == metric_def.numerator_field,
                )
                .scalar() or 0
            )
            rate = num_users / denom_users if denom_users > 0 else 0
            group_results[g.group_name] = {
                "mean": rate,
                "std": (rate * (1 - rate)) ** 0.5,  # 二项分布标准差
                "n": denom_users,
            }

        elif metric_def.metric_type == "count":
            total = (
                session.query(func.count(EventLog.id))
                .filter(
                    EventLog.experiment_id == experiment_id,
                    EventLog.group_id == g.id,
                    EventLog.event_type == metric_def.numerator_field,
                )
                .scalar() or 0
            )
            group_results[g.group_name] = {
                "mean": total,
                "std": total ** 0.5,  # 泊松近似
                "n": denom_users,
            }

    return {
        "metric_name": metric_def.name,
        "metric_type": metric_def.metric_type,
        "category": metric_def.category,
        "groups": group_results,
    }


def compute_daily_metric(session: Session, experiment_id: int,
                         metric_def: MetricDefinition) -> pd.DataFrame:
    """按天计算各组指标值，返回时间序列 DataFrame"""
    from models import EventLog as EL

    groups = session.query(ExperimentGroup).filter_by(experiment_id=experiment_id).all()
    rows = []

    for g in groups:
        dates = (
            session.query(func.distinct(EL.event_date))
            .filter(EL.experiment_id == experiment_id, EL.group_id == g.id)
            .order_by(EL.event_date)
            .all()
        )
        for (d,) in dates:
            if metric_def.denominator_field:
                denom = (
                    session.query(func.count(func.distinct(EL.user_id)))
                    .filter(
                        EL.experiment_id == experiment_id,
                        EL.group_id == g.id,
                        EL.event_date == d,
                        EL.event_type == metric_def.denominator_field,
                    )
                    .scalar() or 0
                )
            else:
                denom = (
                    session.query(func.count(func.distinct(EL.user_id)))
                    .filter(
                        EL.experiment_id == experiment_id,
                        EL.group_id == g.id,
                        EL.event_date == d,
                    )
                    .scalar() or 0
                )

            if metric_def.metric_type == "continuous":
                if "page_view" in (metric_def.numerator_field or ""):
                    agg_col = func.count(EL.id).label("user_val")
                else:
                    agg_col = func.sum(EL.event_value).label("user_val")

                subq = (
                    session.query(EL.user_id, agg_col)
                    .filter(
                        EL.experiment_id == experiment_id,
                        EL.group_id == g.id,
                        EL.event_date == d,
                        EL.event_type == metric_def.numerator_field,
                    )
                    .group_by(EL.user_id)
                    .subquery()
                )
                val = session.query(func.avg(subq.c.user_val)).scalar() or 0
            elif metric_def.metric_type == "proportion":
                num = (
                    session.query(func.count(func.distinct(EL.user_id)))
                    .filter(
                        EL.experiment_id == experiment_id,
                        EL.group_id == g.id,
                        EL.event_date == d,
                        EL.event_type == metric_def.numerator_field,
                    )
                    .scalar() or 0
                )
                val = num / denom if denom > 0 else 0
            else:
                val = (
                    session.query(func.count(EL.id))
                    .filter(
                        EL.experiment_id == experiment_id,
                        EL.group_id == g.id,
                        EL.event_date == d,
                        EL.event_type == metric_def.numerator_field,
                    )
                    .scalar() or 0
                )

            rows.append({
                "date": d,
                "group_name": g.group_name,
                "value": val,
            })

    return pd.DataFrame(rows)
