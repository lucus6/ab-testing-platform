"""DataFly AB实验平台 — Streamlit 入口"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from database import init_db, get_session
import models

st.set_page_config(
    page_title="DataFly AB实验平台",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()


def _restore_session():
    """通过 URL query param 恢复登录态"""
    params = st.experimental_get_query_params()
    token = params.get("token", [None])[0]
    if token:
        s = get_session()
        try:
            from services.auth_service import validate_session
            user = validate_session(s, token)
            if user:
                st.session_state.user = {"id": user.id, "username": user.username, "token": token}
                return
        finally:
            s.close()
    st.session_state.user = None


# ── 登录态恢复 ────────────────────────────────────────────
if "user" not in st.session_state:
    _restore_session()


# ═══════════════════════════════════════════════════════════
# 认证页面
# ═══════════════════════════════════════════════════════════
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
                from services.auth_service import login_user
                s = get_session()
                try:
                    token = login_user(s, username.strip(), password)
                    if token:
                        user = s.query(models.User).filter_by(username=username.strip()).first()
                        st.session_state.user = {"id": user.id, "username": user.username, "token": token}
                        st.experimental_set_query_params(token=token)
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
                    from services.auth_service import register_user
                    s = get_session()
                    try:
                        register_user(s, new_username.strip(), new_pwd, new_email.strip())
                        st.success("注册成功！请切换到「登录」tab 进行登录")
                    except ValueError as e:
                        st.error(str(e))
                    finally:
                        s.close()


# ═══════════════════════════════════════════════════════════
# 主应用
# ═══════════════════════════════════════════════════════════
def _show_main_app():
    user = st.session_state.user

    with st.sidebar:
        st.markdown(f"## ✈️ DataFly")
        st.markdown(f"👤 **{user['username']}**")
        st.markdown("---")

        page = st.radio(
            "导航",
            ["📋 实验管理", "📊 实验详情", "📈 结果分析", "👤 用户中心"],
            label_visibility="collapsed",
        )

        st.markdown("---")

    if page == "📋 实验管理":
        from ui.pages.experiments import show
    elif page == "📊 实验详情":
        from ui.pages.experiment_detail import show
    elif page == "📈 结果分析":
        from ui.pages.results import show
    elif page == "👤 用户中心":
        _show_user_center()
        return
    else:
        return

    show()


def _show_user_center():
    from services.auth_service import change_password, logout_session
    user = st.session_state.user

    st.title("👤 用户中心")

    tab1, tab2, tab3 = st.tabs(["基本信息", "修改密码", "账户安全"])

    with tab1:
        s = get_session()
        try:
            u = s.query(models.User).filter_by(id=user["id"]).first()
            if u:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("用户名", u.username)
                    st.metric("邮箱", u.email or "未填写")
                with col2:
                    st.metric("注册时间", u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "-")
            else:
                st.warning("用户信息加载失败")
        finally:
            s.close()

    with tab2:
        with st.form("change_pwd_form"):
            st.markdown("**修改密码**")
            old_pwd = st.text_input("当前密码", type="password", key="old_pwd")
            new_pwd = st.text_input("新密码（至少6位）", type="password", key="new_pwd")
            new_pwd2 = st.text_input("确认新密码", type="password", key="new_pwd3")
            submitted = st.form_submit_button("确认修改", type="primary")
            if submitted:
                if new_pwd != new_pwd2:
                    st.error("两次密码不一致")
                elif len(new_pwd) < 6:
                    st.error("密码长度至少 6 位")
                else:
                    s = get_session()
                    try:
                        ok = change_password(s, user["id"], old_pwd, new_pwd)
                        if ok:
                            st.success("密码修改成功！")
                        else:
                            st.error("当前密码错误")
                    finally:
                        s.close()

    with tab3:
        st.markdown("### 退出登录")
        st.caption("跳转到登录页，不会删除任何数据。")
        if st.button("🚪 退出登录", key="btn_logout"):
            s = get_session()
            try:
                logout_session(s, user.get("token", ""))
            finally:
                s.close()
            st.session_state.user = None
            st.experimental_set_query_params()
            st.experimental_rerun()

        st.markdown("---")
        st.markdown("### 注销账户")
        st.warning("⚠️ 注销后你的账户和所有实验数据将被**永久删除**，不可恢复。")

        # 确认机制
        if "confirm_delete_account" not in st.session_state:
            st.session_state.confirm_delete_account = False

        if not st.session_state.confirm_delete_account:
            if st.button("🗑 注销账户", key="btn_delete_account", type="secondary"):
                st.session_state.confirm_delete_account = True
                st.experimental_rerun()
        else:
            st.error("确定要注销账户吗？此操作不可撤销！")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ 确认注销", key="btn_confirm_delete"):
                    from services.auth_service import delete_account
                    s = get_session()
                    try:
                        delete_account(s, user["id"])
                    finally:
                        s.close()
                    st.session_state.user = None
                    st.session_state.confirm_delete_account = False
                    st.experimental_set_query_params()
                    st.experimental_rerun()
            with col2:
                if st.button("❌ 取消", key="btn_cancel_delete"):
                    st.session_state.confirm_delete_account = False
                    st.experimental_rerun()


# ═══════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════
if st.session_state.user is None:
    _show_auth_page()
else:
    _show_main_app()
