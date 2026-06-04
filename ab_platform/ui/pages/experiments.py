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

    # 初始化确认状态
    if "confirm" not in st.session_state:
        st.session_state.confirm = None  # 格式: {"action": "delete"/"status", "exp_id": x, "new_status": "..."}

    tab1, tab2 = st.tabs(["实验列表", "新建实验"])

    with tab1:
        _show_experiment_list(user)

    with tab2:
        _show_create_form(user)


def _show_experiment_list(user):
    session = get_session()
    try:
        experiments = list_experiments(session)

        # ── 筛选栏 ──
        col_filter, col_status, col_search = st.columns([1.5, 1.5, 2])
        with col_filter:
            owner_filter = st.radio(
                "归属筛选",
                ["全部实验", "我的实验"],
                horizontal=True,
                key="owner_filter",
                label_visibility="collapsed",
            )
        with col_status:
            status_options = ["全部状态"] + [STATUS_LABELS[s] for s in ["draft", "ramp_up", "running", "paused", "ended"]]
            status_filter = st.selectbox("状态筛选", status_options, key="status_filter", label_visibility="collapsed")
        with col_search:
            search_keyword = st.text_input("搜索", placeholder="实验名称/编号...", key="search_keyword", label_visibility="collapsed")

        # ── 应用筛选 ──
        filtered = experiments
        if owner_filter == "我的实验":
            filtered = [e for e in filtered if e.creator_id == user["id"]]
        if status_filter != "全部状态":
            status_map_rev = {v: k for k, v in STATUS_LABELS.items()}
            target_status = status_map_rev.get(status_filter)
            if target_status:
                filtered = [e for e in filtered if e.status == target_status]
        if search_keyword.strip():
            kw = search_keyword.strip().lower()
            filtered = [
                e for e in filtered
                if kw in e.name.lower() or kw in e.experiment_code.lower() or kw in e.creator.username.lower()
            ]

        st.caption(f"共 {len(filtered)} / {len(experiments)} 个实验")

        if not filtered:
            st.info("没有匹配的实验")
            return

        for exp in filtered:
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

        # ── 确认弹窗（渲染在列表末尾）──
        _render_confirm_dialog(session, user)

    finally:
        session.close()


def _show_status_buttons(session, exp, user):
    is_owner = exp.creator_id == user["id"]
    if not is_owner:
        st.caption("🔒 仅创建者可操作")
        return

    confirm = st.session_state.confirm
    cols = st.columns(3)
    idx = 0

    if exp.status == "draft":
        if cols[idx].button("▶ 灰度", key=f"ramp_{exp.id}"):
            _request_confirm("status", exp, "ramp_up", f"启动灰度：'{exp.name}' ？")
        idx += 1
        if cols[idx].button("🗑 删除", key=f"del_{exp.id}"):
            _request_confirm("delete", exp, None, f"删除实验：'{exp.name}' ？此操作不可恢复！")
    elif exp.status == "ramp_up":
        if cols[0].button("▶ 全量", key=f"run_{exp.id}"):
            _request_confirm("status", exp, "running", f"全量运行：'{exp.name}' ？")
        if cols[1].button("⏸ 暂停", key=f"pause_{exp.id}"):
            _request_confirm("status", exp, "paused", f"暂停实验：'{exp.name}' ？")
    elif exp.status == "running":
        if cols[0].button("⏸ 暂停", key=f"pause2_{exp.id}"):
            _request_confirm("status", exp, "paused", f"暂停实验：'{exp.name}' ？")
        if cols[1].button("⏹ 结束", key=f"end_{exp.id}"):
            _request_confirm("status", exp, "ended", f"结束实验：'{exp.name}' ？")
    elif exp.status == "paused":
        if cols[0].button("▶ 恢复", key=f"resume_{exp.id}"):
            _request_confirm("status", exp, "running", f"恢复运行：'{exp.name}' ？")
        if cols[1].button("⏹ 结束", key=f"end2_{exp.id}"):
            _request_confirm("status", exp, "ended", f"结束实验：'{exp.name}' ？")


def _request_confirm(action, exp, new_status, msg):
    st.session_state.confirm = {
        "action": action,
        "exp_id": exp.id,
        "exp_name": exp.name,
        "new_status": new_status,
        "message": msg,
    }
    st.experimental_rerun()


def _render_confirm_dialog(session, user):
    confirm = st.session_state.confirm
    if confirm is None:
        return

    st.markdown("---")
    st.warning(f"⚠️ {confirm['message']}")

    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        if st.button("✅ 确认", key="confirm_yes"):
            try:
                if confirm["action"] == "delete":
                    ok = delete_experiment(session, confirm["exp_id"], creator_id=user["id"])
                    if ok:
                        st.success("已删除")
                    else:
                        st.error("删除失败")
                elif confirm["action"] == "status":
                    update_experiment_status(session, confirm["exp_id"], confirm["new_status"])
                    st.success(f"状态已更新为「{STATUS_LABELS[confirm['new_status']]}」")
            except Exception as e:
                st.error(f"操作失败：{e}")
            st.session_state.confirm = None
            st.experimental_rerun()
    with col2:
        if st.button("❌ 取消", key="confirm_no"):
            st.session_state.confirm = None
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
                # 表单内的预览确认
                st.info(f"确认创建实验 **{name}**？创建人：{user['username']}，流量：{traffic}%")
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
