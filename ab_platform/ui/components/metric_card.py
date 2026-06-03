"""指标卡片组件"""
import streamlit as st


def metric_card(result: dict):
    """渲染单个指标的统计结果卡片"""
    is_sig = result.get("is_significant", False)
    p_val = result.get("p_value")
    lift = result.get("lift_pct")
    ci_low = result.get("ci_lower_pct")
    ci_up = result.get("ci_upper_pct")

    # 背景色
    if is_sig and lift is not None:
        bg = "#e8f5e9" if lift > 0 else "#ffebee"
        border = "2px solid #4caf50" if lift > 0 else "2px solid #f44336"
    else:
        bg = "#f5f5f5"
        border = "1px solid #e0e0e0"

    # 格式化的 p 值
    if p_val is None:
        p_str = "N/A"
    elif p_val < 0.001:
        p_str = "< 0.001"
    else:
        p_str = f"{p_val:.4f}"

    sig_icon = "✅" if is_sig else "⬜"
    lift_str = f"{lift:+.2f}%" if lift is not None else "N/A"
    ci_str = f"[{ci_low:+.2f}%, {ci_up:+.2f}%]" if ci_low is not None and ci_up is not None else "[-]"

    st.markdown(f"""
    <div style="background:{bg}; border:{border}; border-radius:8px; padding:12px; margin:4px 0;">
        <div style="font-weight:600; font-size:14px;">{sig_icon} {result['metric_name']}</div>
        <div style="display:flex; justify-content:space-between; margin-top:6px;">
            <span style="color:#666; font-size:12px;">{result.get('category', '')}</span>
            <span style="color:#666; font-size:12px;">{result.get('method', '')}</span>
        </div>
        <div style="display:flex; justify-content:space-between; margin-top:8px;">
            <div>
                <span style="font-size:11px; color:#999;">对照组</span><br>
                <span style="font-weight:600;">{_fmt(result.get('control_mean'))}</span>
            </div>
            <div>
                <span style="font-size:11px; color:#999;">实验组</span><br>
                <span style="font-weight:600;">{_fmt(result.get('treatment_mean'))}</span>
            </div>
            <div>
                <span style="font-size:11px; color:#999;">提升</span><br>
                <span style="font-weight:600; color:{'#4caf50' if lift and lift > 0 else '#f44336' if lift and lift < 0 else '#333'};">
                    {lift_str}
                </span>
            </div>
        </div>
        <div style="margin-top:6px; font-size:12px; color:#888;">
            p={p_str} &nbsp; CI: {ci_str}
        </div>
    </div>
    """, unsafe_allow_html=True)


def _fmt(val) -> str:
    if val is None:
        return "N/A"
    if isinstance(val, float):
        if abs(val) >= 100:
            return f"{val:.1f}"
        elif abs(val) >= 1:
            return f"{val:.3f}"
        else:
            return f"{val:.5f}"
    return str(val)
