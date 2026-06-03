"""数据模拟器：模拟真实用户行为日志"""
import random
import hashlib
from datetime import date, timedelta, datetime
from typing import Optional
from sqlalchemy.orm import Session
from models import Experiment, ExperimentGroup, EventLog
from services.bucketing_service import assign_user


class DataSimulator:
    """AB实验数据模拟器"""

    def __init__(self, session: Session):
        self.session = session
        self.users: dict[str, dict] = {}  # user_id -> profile

    def generate_users(self, n_users: int = 2000):
        """生成用户画像"""
        self.users = {}
        regions = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京"]
        for i in range(n_users):
            uid = f"user_{i:06d}"
            seed = int(hashlib.md5(uid.encode()).hexdigest(), 16)
            rng = random.Random(seed)
            self.users[uid] = {
                "user_id": uid,
                "is_new": rng.random() < 0.35,  # 35% 新用户
                "activity_level": rng.choice(["low", "mid", "high"]),  # 活跃度
                "region": rng.choice(regions),
                "base_active_days": rng.randint(2, 7),  # 每周基础活跃天数
                "base_page_views": self._sample_views_per_session(rng),
                "base_click_prob": rng.uniform(0.05, 0.30),
                "base_purchase_prob": rng.uniform(0.01, 0.08),
            }
        return self.users

    def _sample_views_per_session(self, rng: random.Random) -> int:
        """幂律分布模拟单次访问的页面浏览数"""
        return min(rng.randint(1, 3) + int(rng.paretovariate(1.5)), 20)

    def simulate_events(
        self,
        experiment: Experiment,
        days: int = 14,
        n_users: int = 2000,
        effect_size: float = 0.05,  # 实验组提升比例
        pre_experiment_days: int = 7,  # 实验前的历史数据天数
    ):
        """生成模拟事件日志"""
        if not self.users:
            self.generate_users(n_users)

        events = []
        today = date.today()
        start_date = today - timedelta(days=days + pre_experiment_days)
        exp_start_date = today - timedelta(days=days)

        current_date = start_date
        while current_date < today:
            is_pre_experiment = current_date < exp_start_date
            is_weekend = current_date.weekday() >= 5
            daily_users_n = int(len(self.users) * (0.3 if not is_weekend else 0.22))

            # 按活跃度加权采样当天的活跃用户
            active_pool = list(self.users.values())
            weights = {"high": 1.0, "mid": 0.55, "low": 0.25}
            active_weights = [weights[u["activity_level"]] for u in active_pool]
            daily_active = random.choices(active_pool, weights=active_weights, k=daily_users_n)

            for user in daily_active:
                uid = user["user_id"]
                exp = experiment

                # 判断用户分组
                if not is_pre_experiment:
                    assignment = assign_user(uid, exp)
                    if not assignment["in_experiment"]:
                        continue
                    group_id = assignment["group_id"]
                    group_name = assignment["group_name"]
                else:
                    group_id = None
                    group_name = None

                # 生成事件序列
                # 1. exposure（实验曝光）
                if not is_pre_experiment and random.random() < 0.95:
                    events.append(_make_event(uid, exp.id, group_id, "exposure", None, current_date))

                # 2. page_view (event_value=1 用于计算人均)
                n_views = user["base_page_views"]
                if is_weekend:
                    n_views = max(1, int(n_views * 0.7))
                for _ in range(n_views):
                    ev = _make_event(uid, exp.id, group_id, "page_view", 1.0, current_date)
                    events.append(ev)

                # 3. click（实验组效应注入）
                base_click = user["base_click_prob"]
                if not is_pre_experiment and group_name and "实验" in group_name:
                    click_prob = base_click * (1 + effect_size)
                else:
                    click_prob = base_click
                if random.random() < click_prob:
                    events.append(_make_event(uid, exp.id, group_id, "click", 1.0, current_date))

                # 4. purchase（实验组效应注入）
                base_purchase = user["base_purchase_prob"]
                if not is_pre_experiment and group_name and "实验" in group_name:
                    purchase_prob = base_purchase * (1 + effect_size)
                else:
                    purchase_prob = base_purchase
                if random.random() < purchase_prob:
                    amount = round(random.uniform(20, 500), 2)
                    events.append(_make_event(uid, exp.id, group_id, "purchase", amount, current_date))

            current_date += timedelta(days=1)

        # 批量写入
        chunk_size = 500
        for i in range(0, len(events), chunk_size):
            self.session.bulk_save_objects(events[i : i + chunk_size])
        self.session.commit()
        return len(events)


def _make_event(user_id: str, exp_id: int, group_id: Optional[int],
                event_type: str, event_value: Optional[float],
                event_date: date) -> EventLog:
    return EventLog(
        user_id=user_id,
        experiment_id=exp_id,
        group_id=group_id,
        event_type=event_type,
        event_value=event_value,
        event_date=event_date,
        timestamp=datetime.now(),
    )
