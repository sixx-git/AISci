from executors.base import BaseExecutor
from executors.simulation import SimulationExecutor
from executors.sandbox import SandboxExecutor
from executors.data_adapter import (
    DataConfig, BaseDataAdapter, get_adapter, load_data_from_config,
    ADAPTER_REGISTRY,
)
from executors.dataset_profile import (
    DatasetProfile, FilenameParser, PathParser, SensorMerge,
    get_profile, list_profiles,
    SISFALL_PROFILE, MOBIACT_PROFILE, UCI_HAR_PROFILE,
)

# 懒加载注册 directory loader（避免循环导入）
try:
    from executors.directory_loader import DirectoryLoader
    ADAPTER_REGISTRY["directory"] = DirectoryLoader()
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"DirectoryLoader 注册失败: {e}")
