"""Streamlit 入口 - 多页面导航"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from database import init_db
import models  # 确保 ORM 表注册到 metadata

st.set_page_config(
    page_title="AB实验平台",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 初始化数据库
init_db()

# 侧边栏导航
st.sidebar.title("🧪 AB实验平台")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "导航",
    ["📋 实验管理", "📊 实验详情", "📈 结果分析"],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.caption("模拟互联网大厂AB实验平台")

if page == "📋 实验管理":
    from ui.pages.experiments import show
    show()
elif page == "📊 实验详情":
    from ui.pages.experiment_detail import show
    show()
elif page == "📈 结果分析":
    from ui.pages.results import show
    show()
