# 联邦学习 Starter Pack

> **定位**：内容注入（文献种子 / 数据集元数据 / 本地可跑脚本），**不是**多机联邦 runtime。  
> 旧 `skills/federated_experiment/` 技能栈已退役；Pipeline 阶段与 general 完全一致。

## 目录

| 路径 | 说明 |
|------|------|
| `manifest.json` | 包版本与资源索引 |
| `papers/` | 预解析文献 facts（可 seed 到项目） |
| `datasets/` | 数据集 YAML 元数据（schema / 划分 / 下载） |
| `scripts/` | 单机 pilot 参考脚本（sklearn/numpy，无 Flower） |
| `checklists/` | HFL / VFL 指标与写作清单 |
| `failure_cases/` | 失败/反例样例（供报告讨论） |

## 领域标签（v1.3+）

### 方法基座（始终挂载）

| domain | 内容 |
|--------|------|
| `fl_core` | 经典 HFL/VFL（FedAvg、FedProx、LEAF、SplitNN…） |

### 经典应用

| domain | 内容 |
|--------|------|
| `finance_risk` | 金融风控：反欺诈、信用评分、跨机构 VFL |
| `smart_care` | 医疗健康 / 智慧康养：多中心疾病预测、影像、跌倒检测 |
| `edge_mobile` | 智能终端与边缘：输入法、语音助手、推荐、边缘网络 |
| `iot_industrial` | 物联网 / 工业互联网：预测性维护、能耗优化 |
| `smart_transport` | 智慧交通 / 车联网流量预测 |

### 交叉融合

| domain | 内容 |
|--------|------|
| `privacy_crypto` | 差分隐私 / 安全聚合（SMC） |
| `fl_cv` | 联邦计算机视觉（多摄像头检测/识别） |
| `fl_nlp` | 联邦 NLP（对话、输入法、语言模型） |
| `fl_multilingual` | 联邦多语言 / 跨语言（语种分区、低资源语） |
| `llm_ft` | 联邦大模型 / PEFT（LoRA、OpenFedLLM…） |
| `fl_lora_hetero` | 客户端 LoRA 异构（秩/模块/算力差异与对齐聚合） |
| `fl_blockchain` | 区块链：身份认证、聚合审计、激励 |
| `fl_rl` | 联邦强化学习（策略/价值网络参数共享） |
| `fl_continual` | 持续 / 增量学习（Non-IID + 概念漂移） |

## 实验范式（v1.4+）

默认档位 **标准 Non-IID（Dirichlet α=0.1 + FedAvg/FedProx）**。详见 [FL_EXPERIMENT_PARADIGMS.md](./FL_EXPERIMENT_PARADIGMS.md)。

## 启用方式

1. 创建项目时选择模式 **联邦学习（资源包）**，并选 HFL / VFL。
2. 选择实验范式档位（默认标准 Non-IID）；可选勾选经典应用 / 交叉融合领域。
3. 系统写入 `project.config.fl_pack`（按子场景 + 领域 + 档位裁剪），并**自动应用 pack_d**。
4. 项目概览显示「已挂载 FL Pack」版本、档位与 counts；迭代实验可一键把参考脚本写入 `analysis_script`。

环境开关：`AISCI_FL_PACK_ENABLED=true`（默认开启）。

## 重新生成资源

```bash
cd backend
python scripts/generate_fl_starter_pack.py
```

## 手动导入

```bash
cd backend
python -c "from app.services.fl_pack_service import get_fl_pack_service; print(get_fl_pack_service().summary())"
```
