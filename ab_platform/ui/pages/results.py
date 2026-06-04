"""结果分析页：指标卡片 + 趋势图 + 置信区间"""
import streamlit as st
from database import get_session
from services.experiment_service import list_experiments, get_experiment, STATUS_LABELS
from services.metrics_service import get_all_metrics, compute_daily_metric, init_default_metrics
from services.stats_service import analyze_experiment, get_significance_summary
from ui.components.metric_card import metric_card
from ui.components.charts import time_series_chart, confidence_interval_chart


def show():
    st.title("📈 结果分析")

    session = get_session()
    try:
        _select_and_analyze(session)
    finally:
        session.close()


def _select_and_analyze(session):
    exps = list_experiments(session)  # 所有人可见所有实验
    if not exps:
        st.warning("暂无实验，请先在实验管理页创建并模拟数据")
        return

    options = {f"[{STATUS_LABELS[e.status]}] {e.name} ({e.experiment_code})": e.id for e in exps}
    selected = st.selectbox("选择实验", list(options.keys()))
    if not selected:
        return

    exp_id = options[selected]
    exp = get_experiment(session, exp_id)

    # 初始化指标
    init_default_metrics(session)
    metrics = get_all_metrics(session)

    st.markdown(f"**实验：** {exp.name}  |  **状态：** {STATUS_LABELS[exp.status]}  |  **流量：** {exp.total_traffic_pct:.0f}%")

    # 执行分析
    with st.spinner("正在进行统计分析..."):
        results = analyze_experiment(session, exp_id)

    if not results:
        st.warning("未找到可分析的指标数据。请先在「实验详情 → 数据模拟」生成事件数据。")
        return

    # 汇总
    summary = get_significance_summary(results)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("指标总数", summary["total_metrics"])
    with col2:
        st.metric("显著指标", summary["significant_metrics"], delta="有信号" if summary["significant_metrics"] > 0 else None)
    with col3:
        st.metric("显著北极星指标", summary["significant_north_star"])
    with col4:
        has_sig = summary["has_positive_signal"]
        st.metric("实验结论", "🔔 有显著提升" if has_sig else "无显著差异")

    st.markdown("---")

    # 指标卡片 + 时间序列
    st.subheader("📊 指标详情")
    for i, r in enumerate(results):
        with st.expander(f"{'✅' if r.get('is_significant') else '⬜'} {r['metric_name']} — "
                         f"提升 {_fmt_lift(r.get('lift_pct'))} (p={_fmt_p(r.get('p_value'))})",
                         expanded=(i == 0)):
            col_card, col_ts = st.columns([1, 2])
            with col_card:
                metric_card(r)
            with col_ts:
                metric_def = next((m for m in metrics if m.name == r["metric_name"]), None)
                if metric_def:
                    daily_df = compute_daily_metric(session, exp_id, metric_def)
                    fig = time_series_chart(daily_df, r["metric_name"])
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # 置信区间森林图
    st.subheader("🌲 置信区间森林图")
    fig_ci = confidence_interval_chart(results)
    if fig_ci:
        st.plotly_chart(fig_ci, use_container_width=True)

    # 样本量评估
    st.markdown("---")
    st.subheader("📏 样本量评估")
    for r in results:
        n_ctrl = r.get("control_n", 0)
        n_treat = r.get("treatment_n", 0)
        st.caption(f"{r['metric_name']}：对照组 n={n_ctrl}, 实验组 n={n_treat}")


def _fmt_p(p) -> str:
    if p is None:
        return "N/A"
    if p < 0.001:
        return "<0.001"
    return f"{p:.4f}"


def _fmt_lift(l) -> str:
    if l is None:
        return "N/A"
    return f"{l:+.2f}%"
