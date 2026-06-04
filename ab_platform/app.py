"""DataFly AB实验平台 — Streamlit 入口"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from database import init_db, get_session
import models
import json
import os as _os

st.set_page_config(
    page_title="DataFly AB实验平台",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()


def _restore_session():
    """双通道恢复登录态：URL query param + 本地缓存文件"""
    from services.auth_service import validate_session

    token = None
    # 通道1: URL query param
    params = st.experimental_get_query_params()
    token = params.get("token", [None])[0]

    # 通道2: 本地缓存文件
    if not token:
        cache_dir = _os.path.join(_os.path.dirname(__file__), ".cache")
        if _os.path.exists(cache_dir):
            for fname in _os.listdir(cache_dir):
                if fname.endswith(".session"):
                    try:
                        with open(_os.path.join(cache_dir, fname)) as f:
                            data = json.load(f)
                        token = data.get("token")
                        break
                    except Exception:
                        pass

    if token:
        s = get_session()
        try:
            user = validate_session(s, token)
            if user:
                st.session_state.user = {"id": user.id, "username": user.username, "token": token}
                # 确保 query param 同步
                st.experimental_set_query_params(token=token)
                return
        finally:
            s.close()

    st.session_state.user = None


def _save_session_cache(token: str):
    """将 token 写入本地缓存文件，用于刷新后恢复"""
    cache_dir = _os.path.join(_os.path.dirname(__file__), ".cache")
    try:
        _os.makedirs(cache_dir, exist_ok=True)
        cache_file = _os.path.join(cache_dir, "session.session")
        with open(cache_file, "w") as f:
            json.dump({"token": token}, f)
    except Exception:
        pass


def _clear_session_cache():
    """清除本地缓存文件"""
    cache_file = _os.path.join(_os.path.dirname(__file__), ".cache", "session.session")
    try:
        if _os.path.exists(cache_file):
            _os.remove(cache_file)
    except Exception:
        pass


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
                        _save_session_cache(token)
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
    from services.auth_service import change_password, logout_session, update_profile
    user = st.session_state.user

    st.title("👤 用户中心")

    tab1, tab2, tab3 = st.tabs(["📝 个人资料", "🔒 修改密码", "⚙️ 账户安全"])

    # ── Tab 1: 个人资料 ──
    with tab1:
        s = get_session()
        try:
            u = s.query(models.User).filter_by(id=user["id"]).first()
            if not u:
                st.warning("用户信息加载失败")
                return

            st.subheader("基本信息")
            info_col1, info_col2, info_col3 = st.columns(3)
            with info_col1:
                st.markdown(f"**用户名**  \n{u.username}")
            with info_col2:
                st.markdown(f"**部门**  \n{u.department or '未设置'}")
            with info_col3:
                st.markdown(f"**职位**  \n{u.position or '未设置'}")

            info_col4, info_col5 = st.columns(2)
            with info_col4:
                st.markdown(f"**邮箱**  \n{u.email or '未设置'}")
            with info_col5:
                reg_time = u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "-"
                st.markdown(f"**注册时间**  \n{reg_time}")

            if u.bio:
                st.markdown(f"**个人简介**  \n{u.bio}")

            st.markdown("---")
            st.subheader("编辑资料")
            with st.form("edit_profile"):
                ec1, ec2 = st.columns(2)
                with ec1:
                    new_department = st.text_input("部门", value=u.department or "", placeholder="如：数据科学部")
                    new_email = st.text_input("邮箱", value=u.email or "", placeholder="如：zhangsan@company.com")
                with ec2:
                    new_position = st.text_input("职位", value=u.position or "", placeholder="如：高级数据分析师")
                new_bio = st.text_area("个人简介", value=u.bio or "", placeholder="一句话介绍自己...", max_chars=300)
                if st.form_submit_button("💾 保存资料", type="primary"):
                    s2 = get_session()
                    try:
                        update_profile(s2, user["id"],
                                       department=new_department,
                                       position=new_position,
                                       email=new_email,
                                       bio=new_bio)
                        st.success("资料已更新！")
                        st.experimental_rerun()
                    finally:
                        s2.close()
        finally:
            s.close()

    # ── Tab 2: 修改密码 ──
    with tab2:
        st.subheader("修改密码")
        with st.form("change_pwd_form"):
            old_pwd = st.text_input("当前密码", type="password", key="old_pwd")
            new_pwd = st.text_input("新密码（至少6位）", type="password", key="new_pwd")
            new_pwd2 = st.text_input("确认新密码", type="password", key="new_pwd3")
            if st.form_submit_button("确认修改", type="primary"):
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

    # ── Tab 3: 账户安全 ──
    with tab3:
        st.subheader("退出登录")
        st.caption("跳转到登录页，不删除任何数据。")
        if st.button("🚪 退出登录", key="btn_logout"):
            s = get_session()
            try:
                logout_session(s, user.get("token", ""))
            finally:
                s.close()
            st.session_state.user = None
            st.experimental_set_query_params()
            _clear_session_cache()
            st.experimental_rerun()

        st.markdown("---")
        st.subheader("注销账户")
        st.warning("⚠️ 注销后你的账户和所有实验数据将被**永久删除**，不可恢复。")

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
                    _clear_session_cache()
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
