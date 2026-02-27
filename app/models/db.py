import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True)  # UUID
    filename = Column(Text, nullable=True)   # 原始上传文件名（多文件时逗号分隔）
    status = Column(String(20), nullable=False, default="pending")  # pending/processing/done/error
    error_msg = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class PolicyRecord(Base):
    """扁平表，每行对应一个支持方向，前 5 个字段在同文件多行间重复。"""

    __tablename__ = "policy_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(36), nullable=False, index=True)

    # 字段 1-5（公共，多行重复）
    项目名称 = Column(String(500), nullable=False)
    政策依据 = Column(Text, nullable=False)
    归口部门 = Column(String(200), nullable=False)
    联系人 = Column(Text, nullable=False)
    申报时间 = Column(String(200), nullable=False)

    # 字段 6-13（每个支持方向独立）
    支持方向 = Column(Text, nullable=False)
    特定方向要求 = Column(Text, nullable=False)
    申报要求 = Column(Text, nullable=False)
    优惠政策 = Column(Text, nullable=False)
    申报材料 = Column(Text, nullable=False)
    申报方式 = Column(Text, nullable=False)
    网站链接 = Column(Text, nullable=False)
    政策有效期 = Column(String(200), nullable=False)
