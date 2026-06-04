"""ORM 模型定义"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    email = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)

    experiments = relationship("Experiment", back_populates="creator")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class Layer(Base):
    __tablename__ = "layers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    total_buckets = Column(Integer, default=10000)
    description = Column(String(500))
    created_at = Column(DateTime, default=datetime.now)

    experiments = relationship("Experiment", back_populates="layer")


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    hypothesis = Column(Text)
    status = Column(String(20), default="draft")
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    total_traffic_pct = Column(Float, default=10.0)
    start_date = Column(Date)
    end_date = Column(Date)
    layer_id = Column(Integer, ForeignKey("layers.id"))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    creator = relationship("User", back_populates="experiments")
    layer = relationship("Layer", back_populates="experiments")
    groups = relationship("ExperimentGroup", back_populates="experiment", cascade="all, delete-orphan")


class ExperimentGroup(Base):
    __tablename__ = "experiment_groups"
    __table_args__ = (
        UniqueConstraint("experiment_id", "group_name", name="uq_experiment_group_name"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    group_name = Column(String(100), nullable=False)  # control / treatment_A / treatment_B
    bucket_range_start = Column(Integer, nullable=False)
    bucket_range_end = Column(Integer, nullable=False)
    traffic_pct = Column(Float, nullable=False)  # 该组占实验流量的比例

    experiment = relationship("Experiment", back_populates="groups")


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, unique=True)
    metric_type = Column(String(20), nullable=False)  # continuous / proportion / count
    numerator_field = Column(String(100))  # 分子事件类型
    denominator_field = Column(String(100))  # 分母事件类型（比率类指标用）
    category = Column(String(50))  # north_star / driver / guardrail
    description = Column(String(500))
    created_at = Column(DateTime, default=datetime.now)


class EventLog(Base):
    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, index=True)
    experiment_id = Column(Integer, index=True)
    group_id = Column(Integer)
    event_type = Column(String(50), nullable=False, index=True)  # exposure / page_view / click / purchase
    event_value = Column(Float)  # 数值型事件的取值
    event_date = Column(Date, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.now, index=True)
