"""全局配置"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'ab_platform.db')}"
TOTAL_BUCKETS = 10000  # 每层的总桶数
DEFAULT_LAYER_NAME = "default_layer"
