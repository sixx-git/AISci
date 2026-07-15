"""
数据集配置描述文件 (DatasetProfile)

每个复杂数据集（尤其是目录级、多文件、传感器分散的数据集）
需要一个 Profile 来描述其结构，DirectoryLoader 根据 Profile 自动加载。
"""
import re
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable
from pathlib import Path

import pandas as pd


@dataclass
class FilenameParser:
    """文件名解析规则"""
    pattern: str = ""  # 正则表达式，如 r"([DF]\d+)_(SA\d+)_(R\d+)\.txt"
    fields: list[str] = field(default_factory=list)  # 捕获组名称，如 ["activity_code", "subject", "trial"]


@dataclass
class PathParser:
    """路径解析规则"""
    # 从路径中提取字段，例如从 "sub1/ADL/STD/STD_acc_1_1.txt" 中提取 subject, type, activity
    path_components: list[int] = field(default_factory=list)  # 路径层级索引，如 [-3, -2] 表示倒数第3、2层
    field_names: list[str] = field(default_factory=list)  # 对应字段名


@dataclass
class SensorMerge:
    """传感器合并策略"""
    enabled: bool = False
    merge_key: str = "sensor"  # 从文件名/路径提取的传感器类型字段名
    merge_columns: list[str] = field(default_factory=list)  # 合并后的列名前缀，如 ["acc_x", "acc_y", "acc_z", "gyro_x", ...]
    align_by: str = ""  # 对齐列（如 timestamp_ns），空字符串表示按顺序拼接


@dataclass
class DatasetProfile:
    """数据集配置文件"""
    name: str = ""
    description: str = ""
    # 模态: tabular | image | audio | mixed
    modality: str = "tabular"
    # 目录扫描
    scan_pattern: str = "**/*"  # glob 模式
    file_extensions: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)  # 排除的文件名模式
    # 多模态媒体
    media_extensions: list[str] = field(default_factory=list)  # [".jpg", ".png"] / [".wav"]
    manifest_pattern: str = ""  # 如 "**/labels.csv" / "**/metadata.csv"
    path_column: str = "file_path"  # manifest 中路径列，或加载后统一列名
    # 文件读取（tabular）
    delimiter: str = " "
    skip_rows: int = 0
    has_header: bool = False
    column_names: list[str] = field(default_factory=list)
    comment_prefix: str = ""  # 注释行前缀，如 "#"
    # 解析规则
    filename_parser: FilenameParser = field(default_factory=FilenameParser)
    path_parser: PathParser = field(default_factory=PathParser)
    sensor_merge: SensorMerge = field(default_factory=SensorMerge)
    # 标签与划分
    label_column: str = ""
    label_mapping: dict = field(default_factory=dict)
    subject_column: str = ""
    activity_column: str = ""
    trial_column: str = ""
    split_strategy: str = "none"  # none, subject_holdout, ratio
    split_ratio: float = 0.7  # 用于 ratio 策略
    # 后处理
    drop_columns: list[str] = field(default_factory=list)  # 加载后删除的列
    # 自定义规则
    custom_rules: dict = field(default_factory=dict)  # 扩展用

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'DatasetProfile':
        # 递归创建嵌套 dataclass
        if "filename_parser" in data and isinstance(data["filename_parser"], dict):
            data["filename_parser"] = FilenameParser(**data["filename_parser"])
        if "path_parser" in data and isinstance(data["path_parser"], dict):
            data["path_parser"] = PathParser(**data["path_parser"])
        if "sensor_merge" in data and isinstance(data["sensor_merge"], dict):
            data["sensor_merge"] = SensorMerge(**data["sensor_merge"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_json(cls, path_or_content: str) -> 'DatasetProfile':
        """从 JSON 文件路径或 JSON 字符串加载 Profile"""
        raw = (path_or_content or "").strip()
        if raw.startswith("{"):
            return cls.from_dict(json.loads(raw))
        with open(raw, 'r', encoding='utf-8') as f:
            return cls.from_dict(json.load(f))

    def to_json(self, path: str):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


# ==================== 预置数据集 Profile ====================

SISFALL_PROFILE = DatasetProfile(
    name="SisFall",
    description="SisFall 跌倒检测数据集：ADL(19种日常活动) + FALL(15种跌倒)，腰部佩戴ADXL345(加速度)和ITG3200(陀螺仪)，200Hz采样",
    scan_pattern="**/*.txt",
    file_extensions=[".txt"],
    delimiter=",",
    skip_rows=0,
    has_header=False,
    column_names=["col_0", "col_1", "col_2", "col_3", "col_4", "col_5", "col_6", "col_7", "col_8"],
    filename_parser=FilenameParser(
        pattern=r"([DF]\d+)_(SA\d+)_(R\d+)\.txt",
        fields=["activity_code", "subject", "trial"],
    ),
    path_parser=PathParser(
        path_components=[-2],  # ADL/ 或 FALL/
        field_names=["activity_type"],
    ),
    sensor_merge=SensorMerge(enabled=False),
    label_column="label",
    label_mapping={},
    subject_column="subject",
    activity_column="activity_code",
    trial_column="trial",
    split_strategy="subject_holdout",
    drop_columns=[],
    custom_rules={
        "strip_suffix": ";",  # 每行以分号结尾，需要去除
        "label_from_activity_code": True,  # D开头=0(非跌倒), F开头=1(跌倒)
    },
)

MOBIACT_PROFILE = DatasetProfile(
    name="MobiAct",
    description="MobiAct v2.0：24名受试者的ADL(9种)和跌倒(4种)数据，智能手机三轴加速度/陀螺仪/方向传感器",
    scan_pattern="**/*.txt",
    file_extensions=[".txt"],
    delimiter=",",
    skip_rows=0,
    has_header=False,
    column_names=["timestamp_ns", "x", "y", "z"],
    comment_prefix="#",
    filename_parser=FilenameParser(
        pattern=r"([A-Z]+)_(acc|gyro|ori)_(\d+)_(\d+)\.txt",
        fields=["activity_code", "sensor_type", "subject_id", "trial"],
    ),
    path_parser=PathParser(
        path_components=[-3, -4],  # 活动类型(ADL/FALLS)和subject
        field_names=["activity_type", "subject_folder"],
    ),
    sensor_merge=SensorMerge(
        enabled=True,
        merge_key="sensor_type",
        merge_columns=["x", "y", "z"],
        align_by="timestamp_ns",
    ),
    label_column="label",
    label_mapping={},
    subject_column="subject_id",
    activity_column="activity_code",
    trial_column="trial",
    split_strategy="subject_holdout",
    drop_columns=[],
    custom_rules={
        "find_data_marker": "@DATA",  # 找到 @DATA 标记后开始读取数据
    },
)

UCI_HAR_PROFILE = DatasetProfile(
    name="UCI_HAR",
    description="UCI HAR 人体活动识别数据集：30名受试者，6种活动，561维预提取特征 + 原始惯性信号",
    scan_pattern="**/X_*.txt",  # 只匹配特征文件，排除 y_*.txt / subject_*.txt / Inertial Signals/
    file_extensions=[".txt"],
    delimiter=r"\s+",  # 正则匹配任意空白（多个连续空格）
    skip_rows=0,
    has_header=False,
    column_names=[],  # 561维特征，由 features.txt 动态加载
    filename_parser=FilenameParser(),
    path_parser=PathParser(),
    sensor_merge=SensorMerge(enabled=False),
    label_column="label",
    label_mapping={
        1: "WALKING", 2: "WALKING_UPSTAIRS", 3: "WALKING_DOWNSTAIRS",
        4: "SITTING", 5: "STANDING", 6: "LAYING",
    },
    subject_column="subject",
    activity_column="label",
    split_strategy="none",  # 已分 train/test
    drop_columns=[],
    custom_rules={
        "load_labels_from_separate_file": True,  # 从同目录的 y_*.txt / subject_*.txt 加载
        "features_file": "features.txt",
        "activity_labels_file": "activity_labels.txt",
    },
)

# Profile 注册表
PROFILE_REGISTRY: dict[str, DatasetProfile] = {
    "SisFall": SISFALL_PROFILE,
    "MobiAct": MOBIACT_PROFILE,
    "UCI_HAR": UCI_HAR_PROFILE,
}


def get_profile(name: str) -> DatasetProfile:
    """获取预置数据集 Profile"""
    profile = PROFILE_REGISTRY.get(name)
    if not profile:
        raise ValueError(f"未知的数据集 Profile: {name}，可用: {list(PROFILE_REGISTRY.keys())}")
    return profile


def list_profiles() -> list[str]:
    """列出所有可用的 Profile 名称"""
    return list(PROFILE_REGISTRY.keys())
