"""认证服务：注册、登录、Session管理、密码哈希"""
import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from models import User, UserSession


def _hash_password(password: str, salt: str = None) -> tuple:
    """PBKDF2-SHA256 哈希密码，返回 (hash_hex, salt_hex)"""
    if salt is None:
        salt = os.urandom(32).hex()
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        100000,
        dklen=64,
    )
    return key.hex(), salt


def register_user(session: Session, username: str, password: str, email: str = "") -> User:
    """注册新用户"""
    if not username or not password:
        raise ValueError("用户名和密码不能为空")
    if len(password) < 6:
        raise ValueError("密码长度至少 6 位")

    existing = session.query(User).filter_by(username=username).first()
    if existing:
        raise ValueError(f"用户名 '{username}' 已被注册")

    pwd_hash, salt = _hash_password(password)
    user = User(
        username=username,
        password_hash=f"{salt}${pwd_hash}",
        email=email,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def login_user(session: Session, username: str, password: str) -> Optional[str]:
    """验证登录，成功返回 session token，失败返回 None"""
    user = session.query(User).filter_by(username=username).first()
    if not user:
        return None
    try:
        salt, pwd_hash = user.password_hash.split("$", 1)
        computed_hash, _ = _hash_password(password, salt)
        if computed_hash != pwd_hash:
            return None
    except (ValueError, AttributeError):
        return None

    # 创建持久化 session，24 小时过期
    token = os.urandom(32).hex()
    us = UserSession(
        user_id=user.id,
        token=token,
        expires_at=datetime.now() + timedelta(hours=24),
    )
    session.add(us)
    # 清理该用户的旧 session
    session.query(UserSession).filter(
        UserSession.user_id == user.id,
        UserSession.expires_at < datetime.now(),
    ).delete()
    session.commit()
    return token


def validate_session(session: Session, token: str) -> Optional[User]:
    """验证 session token，返回 User 或 None"""
    us = (
        session.query(UserSession)
        .filter(
            UserSession.token == token,
            UserSession.expires_at > datetime.now(),
        )
        .first()
    )
    if us:
        return session.query(User).filter_by(id=us.user_id).first()
    return None


def logout_session(session: Session, token: str):
    """删除 session（登出）"""
    session.query(UserSession).filter_by(token=token).delete()
    session.commit()


def change_password(session: Session, user_id: int, old_pwd: str, new_pwd: str) -> bool:
    """修改密码"""
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        return False
    try:
        salt, pwd_hash = user.password_hash.split("$", 1)
        computed_hash, _ = _hash_password(old_pwd, salt)
        if computed_hash != pwd_hash:
            return False
    except (ValueError, AttributeError):
        return False
    new_hash, new_salt = _hash_password(new_pwd)
    user.password_hash = f"{new_salt}${new_hash}"
    session.commit()
    return True
