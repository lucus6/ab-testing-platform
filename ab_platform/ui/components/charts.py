"""图表组件"""
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd


def time_series_chart(daily_df: pd.DataFrame, metric_name: str):
    """指标时间序列对比图"""
    if daily_df.empty:
        return None
    fig = px.line(
        daily_df, x="date", y="value", color="group_name",
        title=f"{metric_name} — 时间序列",
        markers=True,
        color_discrete_sequence=["#636EFA", "#EF553B", "#00CC96", "#AB63FA"],
    )
    fig.update_layout(
        xaxis_title="日期",
        yaxis_title=metric_name,
        legend_title="实验组",
        height=350,
    )
    return fig


def confidence_interval_chart(results: list):
    """置信区间森林图"""
    fig = go.Figure()
    metric_names = []
    lifts = []
    ci_lower = []
    ci_upper = []
    colors = []

    for r in results:
        if r.get("lift_pct") is None:
            continue
        metric_names.append(r["metric_name"])
        lifts.append(r["lift_pct"])
        ci_lower.append(r.get("ci_lower_pct", r["lift_pct"]))
        ci_upper.append(r.get("ci_upper_pct", r["lift_pct"]))
        is_sig = r.get("is_significant", False)
        colors.append("#4caf50" if (is_sig and r["lift_pct"] > 0)
                      else "#f44336" if (is_sig and r["lift_pct"] < 0)
                      else "#9e9e9e")

    # 计算误差线
    error_minus = [lifts[i] - ci_lower[i] for i in range(len(lifts))]
    error_plus = [ci_upper[i] - lifts[i] for i in range(len(lifts))]

    fig.add_trace(go.Scatter(
        x=lifts,
        y=metric_names,
        mode="markers",
        marker=dict(color=colors, size=10),
        error_x=dict(
            type="data",
            symmetric=False,
            array=error_plus,
            arrayminus=error_minus,
            color="#888",
        ),
        name="相对提升",
    ))
    fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_layout(
        title="相对提升 & 95% 置信区间",
        xaxis_title="相对提升 (%)",
        yaxis=dict(categoryorder="array", categoryarray=metric_names),
        height=250,
    )
    return fig


def traffic_pie_chart(groups_info: list):
    """流量分配饼图"""
    labels = [g["name"] for g in groups_info]
    values = [g["traffic_pct"] for g in groups_info]
    fig = px.pie(
        names=labels, values=values,
        title="流量分配",
        color_discrete_sequence=["#636EFA", "#EF553B", "#00CC96", "#AB63FA"],
    )
    fig.update_layout(height=300)
    return fig
