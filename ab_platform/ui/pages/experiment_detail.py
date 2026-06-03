"""实验详情页：分流可视化 + 渐进放量 + 数据模拟触发"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from database import get_session
from services.experiment_service import (
    get_experiment, update_experiment_traffic, update_experiment_status, STATUS_LABELS,
)
from services.bucketing_service import get_bucket_distribution, assign_user, verify_bucket_consistency
from services.data_simulator import DataSimulator
from models import EventLog
from sqlalchemy import func


def show():
    st.title("📊 实验详情")

    session = get_session()
    try:
        _select_experiment(session)
    finally:
        session.close()


def _select_experiment(session):
    """选择要查看的实验"""
    from services.experiment_service import list_experiments
    exps = list_experiments(session)
    if not exps:
        st.warning("暂无实验，请先在实验管理页创建")
        return
    options = {f"[{STATUS_LABELS[e.status]}] {e.name} (ID:{e.id})": e.id for e in exps}
    selected = st.selectbox("选择实验", list(options.keys()))
    if selected:
        exp_id = options[selected]
        exp = get_experiment(session, exp_id)
        _show_detail(session, exp)


def _show_detail(session, exp):
    tab1, tab2, tab3 = st.tabs(["基本信息 & 分流", "渐进放量", "数据模拟"])

    with tab1:
        _show_basic_info(exp)
        _show_bucket_viz(session, exp)

    with tab2:
        _show_ramp_up(session, exp)

    with tab3:
        _show_data_simulation(session, exp)


def _show_basic_info(exp):
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("状态", STATUS_LABELS[exp.status])
    with col2:
        st.metric("总流量占比", f"{exp.total_traffic_pct:.1f}%")
    with col3:
        st.metric("实验组数", len(exp.groups))

    st.markdown(f"**假设：** {exp.hypothesis or '未填写'}")
    st.markdown(f"**负责人：** {exp.owner or '-'}  |  开始：{exp.start_date or '-'}  |  结束：{exp.end_date or '-'}")


def _show_bucket_viz(session, exp):
    st.subheader("🔀 流量分桶可视化")
    dist = get_bucket_distribution(exp)

    # 画桶区间图
    fig = go.Figure()
    colors = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA"]
    for i, g in enumerate(dist["groups"]):
        fig.add_trace(go.Bar(
            x=[g["size"]],
            y=["桶区间"],
            name=g["name"],
            orientation="h",
            marker=dict(color=colors[i % len(colors)]),
            text=f"{g['name']}: [{g['start']}, {g['end']}) {g['size']}桶 ({g['traffic_pct']:.0f}%)",
            textposition="inside",
            insidetextanchor="middle",
        ))
    fig.update_layout(
        barmode="stack",
        title=f"桶区间分布 — {exp.name} (总流量: {exp.total_traffic_pct:.0f}% = {dist['groups'][0]['end'] - dist['groups'][0]['start']} 桶)",
        height=200,
        xaxis_title="桶编号 (0-9999)",
        showlegend=True,
    )
    st.plotly_chart(fig, use_container_width=True)

    # 分桶一致性测试
    st.markdown("**分桶一致性验证**")
    test_uid = st.text_input("输入 User ID 测试分桶", value="user_000001")
    result = assign_user(test_uid, exp)
    col1, col2 = st.columns(2)
    with col1:
        st.metric("是否在实验内", "✅ 是" if result["in_experiment"] else "❌ 否")
    with col2:
        st.metric("分组", result["group_name"] or "-")

    if result["in_experiment"] and verify_bucket_consistency(test_uid, exp):
        st.success(f"✅ 分桶一致性通过：{test_uid} 始终分配到 '{result['group_name']}'")
    elif result["in_experiment"]:
        st.warning("⚠️ 分桶一致性失败！")

    # 事件量统计
    st.markdown("**事件日志统计**")
    counts = (
        session.query(EventLog.event_type, func.count(EventLog.id))
        .filter(EventLog.experiment_id == exp.id)
        .group_by(EventLog.event_type)
        .all()
    )
    if counts:
        df_counts = pd.DataFrame(counts, columns=["事件类型", "数量"])
        cols = st.columns(len(counts))
        for i, (etype, cnt) in enumerate(counts):
            with cols[i]:
                st.metric(etype, cnt)
    else:
        st.caption("暂无事件数据，请先在「数据模拟」tab 生成")


def _show_ramp_up(session, exp):
    st.subheader("📐 渐进放量")
    if exp.status not in ("ramp_up", "running", "paused"):
        st.info("实验未在运行中，无法调整流量。请先在实验管理页将状态改为 灰度/运行中。")
        return

    current = exp.total_traffic_pct
    new_pct = st.slider("调整实验总流量占比", 1.0, 100.0, float(current), 1.0,
                        help="逐步扩大实验覆盖的用户比例")

    if abs(new_pct - current) > 0.1:
        if st.button(f"确认调整 → {new_pct:.0f}%", type="primary"):
            try:
                update_experiment_traffic(session, exp.id, new_pct)
                st.success(f"流量已调整为 {new_pct:.0f}%")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    st.caption("渐进放量建议：1% → 5% → 10% → 25% → 50% → 100%，每步观察至少1天数据")


def _show_data_simulation(session, exp):
    st.subheader("🎲 数据模拟器")
    st.markdown("模拟真实用户行为数据，包括**用户画像**、**周末效应**、**实验效应注入**和**预实验历史数据**")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        n_users = st.number_input("模拟用户数", 200, 10000, 2000, 200)
    with col2:
        sim_days = st.number_input("实验天数", 1, 60, 14)
    with col3:
        effect_size = st.number_input("效应大小 (%)", 0.0, 50.0, 5.0, 1.0, help="实验组相对对照组的提升幅度")
    with col4:
        pre_days = st.number_input("预实验天数", 0, 30, 7, help="实验开始前的历史数据天数")

    existing_count = session.query(func.count(EventLog.id)).filter(
        EventLog.experiment_id == exp.id
    ).scalar()

    if existing_count > 0:
        st.info(f"该实验已有 {existing_count} 条事件记录，重新生成将覆盖旧数据")
        if st.button("⚠️ 清空旧数据并重新生成", type="secondary"):
            session.query(EventLog).filter(EventLog.experiment_id == exp.id).delete()
            session.commit()
            st.rerun()
    else:
        if st.button("🚀 开始生成模拟数据", type="primary", use_container_width=True):
            with st.spinner("正在生成用户画像和事件日志..."):
                try:
                    simulator = DataSimulator(session)
                    total_events = simulator.simulate_events(
                        experiment=exp,
                        days=sim_days,
                        n_users=n_users,
                        effect_size=effect_size / 100.0,
                        pre_experiment_days=pre_days,
                    )
                    st.success(f"✅ 成功生成 {total_events} 条事件记录！")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"生成失败：{e}")
