"""DataFly AB实验平台 — Streamlit 入口"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from database import init_db
import models

st.set_page_config(
    page_title="DataFly AB实验平台",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

# ── 登录态检查 ──────────────────────────────────────────
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    _show_auth_page()
else:
    _show_main_app()


def _show_auth_page():
    st.markdown("""
    <div style="text-align:center; margin-top:60px;">
        <h1 style="font-size:48px;">✈️ DataFly</h1>
        <p style="font-size:18px; color:#888;">AB 实验平台</p>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["登录", "注册"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("用户名", key="login_username")
            password = st.text_input("密码", type="password", key="login_password")
            submitted = st.form_submit_button("登录", type="primary", use_container_width=True)
            if submitted:
                from database import get_session
                from services.auth_service import login_user
                s = get_session()
                try:
                    user = login_user(s, username.strip(), password)
                    if user:
                        st.session_state.user = {"id": user.id, "username": user.username}
                        st.success("登录成功！")
                        st.experimental_rerun()
                    else:
                        st.error("用户名或密码错误")
                finally:
                    s.close()

    with tab_register:
        with st.form("register_form"):
            new_username = st.text_input("用户名", key="reg_username")
            new_email = st.text_input("邮箱（选填）", key="reg_email")
            new_pwd = st.text_input("密码（至少6位）", type="password", key="reg_pwd")
            new_pwd2 = st.text_input("确认密码", type="password", key="reg_pwd2")
            submitted = st.form_submit_button("注册", type="primary", use_container_width=True)
            if submitted:
                if new_pwd != new_pwd2:
                    st.error("两次密码不一致")
                elif len(new_pwd) < 6:
                    st.error("密码长度至少 6 位")
                else:
                    from database import get_session
                    from services.auth_service import register_user
                    s = get_session()
                    try:
                        register_user(s, new_username.strip(), new_pwd, new_email.strip())
                        st.success("注册成功！请切换到「登录」tab 进行登录")
                    except ValueError as e:
                        st.error(str(e))
                    finally:
                        s.close()


def _show_main_app():
    user = st.session_state.user

    # 侧边栏
    with st.sidebar:
        st.markdown(f"## ✈️ DataFly")
        st.markdown(f"👤 **{user['username']}**")
        st.markdown("---")

        page = st.radio(
            "导航",
            ["📋 实验管理", "📊 实验详情", "📈 结果分析"],
            label_visibility="collapsed",
        )

        st.markdown("---")
        if st.button("🚪 退出登录", use_container_width=True):
            st.session_state.user = None
            st.experimental_rerun()

    # 页面路由
    if page == "📋 实验管理":
        from ui.pages.experiments import show
    elif page == "📊 实验详情":
        from ui.pages.experiment_detail import show
    elif page == "📈 结果分析":
        from ui.pages.results import show

    show()
