"""实验管理页面"""
import streamlit as st
from database import get_session
from services.experiment_service import (
    create_experiment,
    list_experiments,
    update_experiment_status,
    delete_experiment,
    STATUS_LABELS,
)
from models import ExperimentGroup


def show():
    st.title("📋 实验管理")
    user = st.session_state.user

    tab1, tab2 = st.tabs(["实验列表", "新建实验"])

    with tab1:
        _show_experiment_list(user)

    with tab2:
        _show_create_form(user)


def _show_experiment_list(user):
    session = get_session()
    try:
        experiments = list_experiments(session, creator_id=user["id"])
        if not experiments:
            st.info("暂无实验，请点击「新建实验」创建")
            return

        for exp in experiments:
            with st.container():
                col1, col2, col3, col4, col5, col6 = st.columns([3, 1.5, 1, 1.5, 2, 2])
                with col1:
                    st.markdown(f"**{exp.name}**")
                    st.caption(f"`{exp.experiment_code}` | 创建人: {exp.creator.username}")
                with col2:
                    status_color = {
                        "draft": "gray", "ramp_up": "orange",
                        "running": "green", "paused": "blue", "ended": "red"
                    }.get(exp.status, "gray")
                    st.markdown(f":{status_color}[{STATUS_LABELS[exp.status]}]")
                with col3:
                    st.metric("流量", f"{exp.total_traffic_pct:.0f}%")
                with col4:
                    st.caption(f"开始: {exp.start_date or '-'}")
                    st.caption(f"结束: {exp.end_date or '-'}")
                with col5:
                    groups = session.query(ExperimentGroup).filter_by(experiment_id=exp.id).all()
                    g_text = " | ".join(f"{g.group_name}({g.traffic_pct:.0f}%)" for g in groups)
                    st.caption(g_text)
                with col6:
                    _show_status_buttons(session, exp, user)
                st.markdown("---")
    finally:
        session.close()


def _show_status_buttons(session, exp, user):
    cols = st.columns(3)
    idx = 0
    if exp.status == "draft":
        if cols[idx].button("▶ 灰度", key=f"ramp_{exp.id}"):
            update_experiment_status(session, exp.id, "ramp_up")
            st.experimental_rerun()
        idx += 1
        if cols[idx].button("🗑 删除", key=f"del_{exp.id}"):
            delete_experiment(session, exp.id, creator_id=user["id"])
            st.experimental_rerun()
    elif exp.status == "ramp_up":
        if cols[0].button("▶ 全量", key=f"run_{exp.id}"):
            update_experiment_status(session, exp.id, "running")
            st.experimental_rerun()
        if cols[1].button("⏸ 暂停", key=f"pause_{exp.id}"):
            update_experiment_status(session, exp.id, "paused")
            st.experimental_rerun()
    elif exp.status == "running":
        if cols[0].button("⏸ 暂停", key=f"pause2_{exp.id}"):
            update_experiment_status(session, exp.id, "paused")
            st.experimental_rerun()
        if cols[1].button("⏹ 结束", key=f"end_{exp.id}"):
            update_experiment_status(session, exp.id, "ended")
            st.experimental_rerun()
    elif exp.status == "paused":
        if cols[0].button("▶ 恢复", key=f"resume_{exp.id}"):
            update_experiment_status(session, exp.id, "running")
            st.experimental_rerun()
        if cols[1].button("⏹ 结束", key=f"end2_{exp.id}"):
            update_experiment_status(session, exp.id, "ended")
            st.experimental_rerun()


def _show_create_form(user):
    st.subheader("新建实验")

    with st.form("create_experiment"):
        st.caption(f"创建人：**{user['username']}**")
        name = st.text_input("实验名称", placeholder="如：首页推荐算法优化")
        hypothesis = st.text_area("实验假设", placeholder="如：新推荐算法能提升用户点击率 5%")
        traffic = st.slider("总流量占比 (%)", 1, 100, 10, help="该实验占总流量的百分比")

        st.markdown("**实验组配置**")
        col1, col2 = st.columns(2)
        with col1:
            ctrl_name = st.text_input("对照组名称", value="对照组")
            ctrl_pct = st.number_input("对照组流量 (%)", 1, 99, 50)
        with col2:
            treat_name = st.text_input("实验组名称", value="实验组")
            treat_pct = st.number_input("实验组流量 (%)", 1, 99, 50)

        submitted = st.form_submit_button("创建实验", type="primary", use_container_width=True)
        if submitted:
            if not name:
                st.error("请输入实验名称")
            else:
                session = get_session()
                try:
                    group_configs = [
                        {"group_name": ctrl_name, "traffic_pct": ctrl_pct},
                        {"group_name": treat_name, "traffic_pct": treat_pct},
                    ]
                    exp = create_experiment(
                        session, name, hypothesis,
                        creator_id=user["id"],
                        total_traffic_pct=traffic,
                        group_configs=group_configs,
                    )
                    st.success(f"实验 '{exp.name}' 创建成功！编号：`{exp.experiment_code}`")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"创建失败：{e}")
                finally:
                    session.close()
