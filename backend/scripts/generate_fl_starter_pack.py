"""Generate FL Starter Pack assets under backend/data/reference/fl/ (run once)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data" / "reference" / "fl"


def w(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip("\n") if text.startswith("\n") else text, encoding="utf-8")
    if not text.endswith("\n"):
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")


PAPERS = [
    {
        "id": "mcmahan2017fedavg",
        "title": "Communication-Efficient Learning of Deep Networks from Decentralized Data",
        "year": 2017,
        "venue": "AISTATS",
        "external_id": "arXiv:1602.05629",
        "setting": "hfl",
        "domain": "fl_core",
        "facts": [
            {
                "fact_id": "fl_seed_fedavg_1",
                "claim": "FedAvg 通过对本地 SGD 更新做加权平均，可在通信受限条件下训练深度模型。",
                "method": "FedAvg",
                "setting": "hfl",
                "domain": "fl_core",
                "metrics": ["global_accuracy", "communication_rounds"],
                "dataset": "MNIST / Shakespeare (LEAF-like)",
                "limitations": "Non-IID 与部分参与会显著影响收敛。",
                "source": "McMahan et al., 2017",
                "quote": "Federated Averaging",
                "relevance": 0.95,
            },
            {
                "fact_id": "fl_seed_fedavg_2",
                "claim": "联邦平均的核心权衡是本地计算量与通信轮次：增加本地 epoch 可减通信，但在 Non-IID 下可能加剧客户端漂移。",
                "method": "FedAvg",
                "setting": "hfl",
                "domain": "fl_core",
                "metrics": ["communication_rounds", "client_drift", "global_accuracy"],
                "dataset": "MNIST / FEMNIST",
                "limitations": "最优本地步数依赖异构程度，不可照搬中心化超参。",
                "source": "McMahan et al., 2017",
                "quote": "local SGD",
                "relevance": 0.9,
            },
        ],
        "data_links": ["https://github.com/TalwalkarLab/leaf"],
        "recommended_baselines": ["FedAvg", "local-only SGD"],
    },
    {
        "id": "li2020fedprox",
        "title": "Federated Optimization in Heterogeneous Networks",
        "year": 2020,
        "venue": "MLSys",
        "external_id": "arXiv:1812.06127",
        "setting": "hfl",
        "domain": "fl_core",
        "facts": [
            {
                "fact_id": "fl_seed_fedprox_1",
                "claim": "FedProx 在本地目标中加入近端项，缓解系统与统计异构下的不稳定。",
                "method": "FedProx",
                "setting": "hfl",
                "domain": "fl_core",
                "metrics": ["global_accuracy", "client_drift"],
                "dataset": "FEMNIST / Sent140",
                "limitations": "近端系数需调参；通信成本仍高。",
                "source": "Li et al., 2020",
                "quote": "proximal term",
                "relevance": 0.92,
            },
            {
                "fact_id": "fl_seed_fedprox_2",
                "claim": "当客户端算力与数据量差异大时，FedProx 比朴素 FedAvg 更适合作为稳健基线，报告应同时给出 μ 与参与率。",
                "method": "FedProx",
                "setting": "hfl",
                "domain": "fl_core",
                "metrics": ["participation_rate", "global_accuracy", "mu"],
                "dataset": "heterogeneous networks",
                "limitations": "μ 过大接近不做本地更新，过小退化为 FedAvg。",
                "source": "Li et al., 2020",
                "quote": "heterogeneous networks",
                "relevance": 0.88,
            },
        ],
        "data_links": ["https://github.com/TalwalkarLab/leaf"],
        "recommended_baselines": ["FedAvg", "FedProx"],
    },
    {
        "id": "caldas2018leaf",
        "title": "LEAF: A Benchmark for Federated Settings",
        "year": 2018,
        "venue": "arXiv",
        "external_id": "arXiv:1812.01097",
        "setting": "hfl",
        "domain": "fl_core",
        "facts": [
            {
                "fact_id": "fl_seed_leaf_1",
                "claim": "LEAF 提供 FEMNIST、Shakespeare 等带自然客户端划分的联邦基准。",
                "method": "benchmark",
                "setting": "hfl",
                "domain": "fl_core",
                "metrics": ["global_accuracy", "num_clients"],
                "dataset": "LEAF suite",
                "limitations": "完整数据体积大，小样验证需子集。",
                "source": "Caldas et al., 2018",
                "quote": "LEAF",
                "relevance": 0.9,
            },
            {
                "fact_id": "fl_seed_leaf_2",
                "claim": "评测联邦算法时应优先使用自然客户端划分基准，并报告客户端规模与样本不均衡，避免仅用人工切 MNIST。",
                "method": "benchmark protocol",
                "setting": "hfl",
                "domain": "fl_core",
                "metrics": ["num_clients", "non_iid_degree", "global_accuracy"],
                "dataset": "LEAF FEMNIST / Shakespeare",
                "limitations": "小样子集需声明抽样规则，否则不可与全文结果对比。",
                "source": "Caldas et al., 2018",
                "quote": "federated settings",
                "relevance": 0.87,
            },
        ],
        "data_links": ["https://github.com/TalwalkarLab/leaf"],
        "recommended_baselines": ["FedAvg"],
    },
    {
        "id": "zhao2018noniid",
        "title": "Federated Learning with Non-IID Data",
        "year": 2018,
        "venue": "arXiv",
        "external_id": "arXiv:1806.00582",
        "setting": "hfl",
        "facts": [
            {
                "fact_id": "fl_seed_noniid_1",
                "claim": "高度 Non-IID 划分可导致 FedAvg 精度显著下降，需更频繁通信或更强正则。",
                "method": "FedAvg + Non-IID analysis",
                "setting": "hfl",
                "metrics": ["global_accuracy", "non_iid_degree"],
                "dataset": "CIFAR / MNIST partitioned",
                "limitations": "划分方式影响结论外推。",
                "source": "Zhao et al., 2018",
                "quote": "non-IID",
                "relevance": 0.9,
            }
        ],
        "data_links": [],
        "recommended_baselines": ["FedAvg", "data sharing"],
    },
    {
        "id": "vepakomma2018splitnn",
        "title": "Split learning for health: Distributed deep learning without sharing raw patient data",
        "year": 2018,
        "venue": "arXiv",
        "external_id": "arXiv:1812.00564",
        "setting": "vfl",
        "facts": [
            {
                "fact_id": "fl_seed_splitnn_1",
                "claim": "SplitNN 将网络按层切开，使各方无需共享原始特征即可协作训练。",
                "method": "SplitNN",
                "setting": "vfl",
                "metrics": ["auc", "aligned_sample_rate"],
                "dataset": "healthcare tabular / imaging",
                "limitations": "依赖可靠样本对齐与中间激活传输。",
                "source": "Vepakomma et al., 2018",
                "quote": "split learning",
                "relevance": 0.88,
            }
        ],
        "data_links": [],
        "recommended_baselines": ["centralized", "SplitNN"],
    },
    {
        "id": "liu2022vflsurvey",
        "title": "A Survey on Vertical Federated Learning: From Concepts to Applications",
        "year": 2022,
        "venue": "survey",
        "external_id": "survey:vfl-2022",
        "setting": "vfl",
        "facts": [
            {
                "fact_id": "fl_seed_vfl_survey_1",
                "claim": "VFL 核心挑战包括实体对齐、特征方/标签方分工、通信与隐私预算权衡。",
                "method": "VFL survey",
                "setting": "vfl",
                "metrics": ["aligned_sample_rate", "privacy_budget", "communication_cost_mb"],
                "dataset": "multi-party tabular",
                "limitations": "综述结论需落到可验证小样实验。",
                "source": "VFL survey literature",
                "quote": "entity alignment",
                "relevance": 0.85,
            }
        ],
        "data_links": [],
        "recommended_baselines": ["logistic VFL", "SplitNN"],
    },
    {
        "id": "bagdasaryan2020backdoor",
        "title": "How To Backdoor Federated Learning",
        "year": 2020,
        "venue": "AISTATS",
        "external_id": "arXiv:1807.00459",
        "setting": "hfl",
        "facts": [
            {
                "fact_id": "fl_seed_backdoor_1",
                "claim": "恶意客户端可通过模型投毒在联邦聚合中植入后门，失败案例需写入局限讨论。",
                "method": "attack analysis",
                "setting": "hfl",
                "metrics": ["backdoor_success_rate", "global_accuracy"],
                "dataset": "CIFAR / Reddit",
                "limitations": "防御与攻击共同演进，单一防御不可外推。",
                "source": "Bagdasaryan et al., 2020",
                "quote": "backdoor",
                "relevance": 0.8,
            }
        ],
        "data_links": [],
        "recommended_baselines": ["FedAvg", "robust aggregation"],
    },
    {
        "id": "kairouz2021advances",
        "title": "Advances and Open Problems in Federated Learning",
        "year": 2021,
        "venue": "Foundations and Trends",
        "external_id": "arXiv:1912.04977",
        "setting": "both",
        "facts": [
            {
                "fact_id": "fl_seed_open_1",
                "claim": "联邦学习开放问题覆盖异构性、隐私、公平性与系统效率，报告应明确所选子问题边界。",
                "method": "survey",
                "setting": "both",
                "metrics": ["communication_rounds", "privacy_budget"],
                "dataset": "various",
                "limitations": "开放问题综述不能替代具体可证伪假设。",
                "source": "Kairouz et al., 2021",
                "quote": "open problems",
                "relevance": 0.86,
            }
        ],
        "data_links": [],
        "recommended_baselines": ["FedAvg", "FedProx"],
    },
    # —— 交叉领域：大模型参数高效微调 / 联邦 LLM ——
    {
        "id": "hu2022lora",
        "title": "LoRA: Low-Rank Adaptation of Large Language Models",
        "year": 2022,
        "venue": "ICLR",
        "external_id": "arXiv:2106.09685",
        "setting": "both",
        "domain": "llm_ft",
        "facts": [
            {
                "fact_id": "fl_seed_lora_1",
                "claim": "LoRA 通过低秩适配矩阵在冻结主干下微调大模型，显著降低可训练参数与通信载荷，是联邦大模型微调的常用基础模块。",
                "method": "LoRA / PEFT",
                "setting": "both",
                "domain": "llm_ft",
                "metrics": ["trainable_params", "downstream_accuracy", "communication_cost_mb"],
                "dataset": "GLUE / instruction-tuning corpora",
                "limitations": "秩与目标模块选择影响效果；不等于已解决联邦隐私。",
                "source": "Hu et al., 2022",
                "quote": "low-rank adaptation",
                "relevance": 0.9,
            },
            {
                "fact_id": "fl_seed_lora_2",
                "claim": "在联邦场景中仅聚合 LoRA 适配器而非全量权重，可把通信成本从全参量级降到适配器量级，便于跨机构协作微调。",
                "method": "FedLoRA-style aggregation",
                "setting": "hfl",
                "domain": "llm_ft",
                "metrics": ["communication_cost_mb", "communication_rounds"],
                "dataset": "multi-client instruction shards",
                "limitations": "客户端数据异构仍会导致适配器漂移。",
                "source": "Hu et al., 2022 + FL PEFT practice",
                "quote": "adapter",
                "relevance": 0.88,
            },
        ],
        "data_links": ["https://arxiv.org/abs/2106.09685"],
        "recommended_baselines": ["full fine-tuning", "LoRA", "FedAvg on adapters"],
    },
    {
        "id": "ye2024openfedllm",
        "title": "OpenFedLLM: Training Large Language Models on Decentralized Private Data via Federated Learning",
        "year": 2024,
        "venue": "arXiv",
        "external_id": "arXiv:2401.06468",
        "setting": "hfl",
        "domain": "llm_ft",
        "facts": [
            {
                "fact_id": "fl_seed_openfedllm_1",
                "claim": "OpenFedLLM 将联邦学习流程系统化用于大语言模型训练/微调，强调私有分散语料上的协作训练框架与评测协议。",
                "method": "FedLLM framework",
                "setting": "hfl",
                "domain": "llm_ft",
                "metrics": ["downstream_accuracy", "communication_rounds", "privacy_notes"],
                "dataset": "federated LLM benchmarks / private corpora",
                "limitations": "算力与带宽门槛高；小样验证需用合成指令分片或 PEFT。",
                "source": "Ye et al., 2024",
                "quote": "OpenFedLLM",
                "relevance": 0.91,
            },
            {
                "fact_id": "fl_seed_openfedllm_2",
                "claim": "联邦 LLM 设定下，客户端应报告本地数据域差异与指令分布，否则全局模型可能偏向主导机构语料。",
                "method": "FedLLM evaluation protocol",
                "setting": "hfl",
                "domain": "llm_ft",
                "metrics": ["client_drift", "global_accuracy"],
                "dataset": "heterogeneous instruction sets",
                "limitations": "公开复现依赖开源分片，真实机构数据不可外发。",
                "source": "Ye et al., 2024",
                "quote": "decentralized private data",
                "relevance": 0.87,
            },
        ],
        "data_links": ["https://arxiv.org/abs/2401.06468"],
        "recommended_baselines": ["centralized SFT", "FedAvg+LoRA", "local-only LoRA"],
    },
    {
        "id": "zhang2023fedpeft",
        "title": "Federated Learning for Large Language Models: Towards Federated PEFT and Instruction Tuning",
        "year": 2023,
        "venue": "community survey / FedPEFT line",
        "external_id": "survey:fed-llm-peft-2023",
        "setting": "hfl",
        "domain": "llm_ft",
        "facts": [
            {
                "fact_id": "fl_seed_fedpeft_1",
                "claim": "联邦参数高效微调（FedPEFT）以提示调优/LoRA 等适配器为聚合对象，是在通信与算力约束下做跨机构指令微调的主流路线。",
                "method": "FedPEFT / FedIT-style",
                "setting": "hfl",
                "domain": "llm_ft",
                "metrics": ["communication_cost_mb", "downstream_accuracy", "trainable_params"],
                "dataset": "instruction-tuning shards",
                "limitations": "需明确冻结层与适配器放置；安全对齐风险仍在。",
                "source": "FedLLM PEFT literature synthesis",
                "quote": "parameter-efficient",
                "relevance": 0.86,
            },
            {
                "fact_id": "fl_seed_fedpeft_2",
                "claim": "指令微调联邦化时，应以任务级指标（如指令遵循准确率）为主指标，并同时报告通信轮次与适配器规模，避免只报中心化 SFT 分数。",
                "method": "Fed instruction tuning metrics",
                "setting": "hfl",
                "domain": "llm_ft",
                "metrics": ["instruction_following_score", "communication_rounds"],
                "dataset": "multi-tenant prompts",
                "limitations": "小样合成指令与真实业务指令分布可能不一致。",
                "source": "FedLLM PEFT literature synthesis",
                "quote": "instruction tuning",
                "relevance": 0.84,
            },
        ],
        "data_links": [],
        "recommended_baselines": ["LoRA SFT", "FedAvg+LoRA", "prompt tuning"],
    },
    # —— 交叉领域：智慧康养 / 可穿戴 / 跌倒检测 ——
    {
        "id": "xu2021flhealth",
        "title": "Federated Learning for Healthcare Informatics",
        "year": 2021,
        "venue": "survey",
        "external_id": "survey:fl-healthcare-2021",
        "setting": "both",
        "domain": "smart_care",
        "facts": [
            {
                "fact_id": "fl_seed_health_1",
                "claim": "医疗健康联邦学习需同时满足临床可用性与隐私合规，数据常呈机构级 Non-IID，且标签定义可能不一致。",
                "method": "FL healthcare survey",
                "setting": "both",
                "domain": "smart_care",
                "metrics": ["auc", "f1_score", "privacy_budget"],
                "dataset": "multi-hospital EHR / imaging",
                "limitations": "综述需落到可验证小样与明确临床终点。",
                "source": "Xu et al., healthcare FL survey line",
                "quote": "healthcare informatics",
                "relevance": 0.9,
            },
            {
                "fact_id": "fl_seed_health_2",
                "claim": "康养/慢病场景中，穿戴设备与院内数据分属不同机构时，更适合用横向联邦或经对齐的垂直联邦，而不是中心化汇聚原始波形。",
                "method": "FL for wearable + hospital collaboration",
                "setting": "both",
                "domain": "smart_care",
                "metrics": ["aligned_sample_rate", "global_accuracy"],
                "dataset": "wearable + EHR",
                "limitations": "时间戳对齐与采样率差异是常见失败源。",
                "source": "healthcare FL practice",
                "quote": "wearable",
                "relevance": 0.88,
            },
        ],
        "data_links": [],
        "recommended_baselines": ["centralized", "FedAvg", "SplitNN"],
    },
    {
        "id": "sisfall_fl_care",
        "title": "Fall Detection and Activity Recognition under Federated Learning Constraints (SisFall/MobiAct line)",
        "year": 2020,
        "venue": "applied FL / HAR",
        "external_id": "applied:sisfall-fl-care",
        "setting": "hfl",
        "domain": "smart_care",
        "facts": [
            {
                "fact_id": "fl_seed_fall_1",
                "claim": "跌倒检测与日常活动识别（HAR）可按受试者/设备划分客户端做横向联邦，避免集中上传原始加速度波形。",
                "method": "FedAvg on HAR / fall detection",
                "setting": "hfl",
                "domain": "smart_care",
                "metrics": ["f1_score", "recall", "global_accuracy", "communication_rounds"],
                "dataset": "SisFall / MobiAct / UCI-HAR style",
                "limitations": "跌倒样本稀少会导致极端 Non-IID；需报告少数类召回。",
                "source": "HAR + FL applied literature",
                "quote": "fall detection",
                "relevance": 0.92,
            },
            {
                "fact_id": "fl_seed_fall_2",
                "claim": "智慧康养联邦实验应以受试者独立划分评估泛化，并记录设备异质（采样率、传感器轴）带来的客户端漂移。",
                "method": "subject-independent FL evaluation",
                "setting": "hfl",
                "domain": "smart_care",
                "metrics": ["client_drift", "f1_score", "non_iid_degree"],
                "dataset": "multi-device wearable",
                "limitations": "实验室跌倒与真实居家跌倒分布不同。",
                "source": "HAR + FL applied literature",
                "quote": "subject-independent",
                "relevance": 0.89,
            },
            {
                "fact_id": "fl_seed_fall_3",
                "claim": "当养老机构只有标签、设备厂商只有特征时，可用垂直联邦思路验证对齐键（如 session_id）与联合判别性能。",
                "method": "VFL-style care collaboration",
                "setting": "vfl",
                "domain": "smart_care",
                "metrics": ["aligned_sample_rate", "auc"],
                "dataset": "feature-party sensors + label-party care records",
                "limitations": "对齐失败会直接导致可用样本骤减。",
                "source": "care VFL scenario design",
                "quote": "alignment",
                "relevance": 0.85,
            },
        ],
        "data_links": [],
        "recommended_baselines": ["local CNN/LSTM", "FedAvg", "centralized"],
    },
    {
        "id": "rieke2020medicalfl",
        "title": "The Future of Digital Health with Federated Learning",
        "year": 2020,
        "venue": "npj Digital Medicine",
        "external_id": "doi:10.1038/s41746-020-00323-1",
        "setting": "both",
        "domain": "smart_care",
        "facts": [
            {
                "fact_id": "fl_seed_npj_1",
                "claim": "数字健康联邦学习强调跨机构协作同时保留数据本地化，是智慧康养/临床 AI 落地的重要治理与技术框架。",
                "method": "digital health FL outlook",
                "setting": "both",
                "domain": "smart_care",
                "metrics": ["privacy_budget", "auc"],
                "dataset": "multi-site clinical data",
                "limitations": "治理与激励问题超出纯算法指标。",
                "source": "Rieke et al., 2020",
                "quote": "digital health",
                "relevance": 0.87,
            }
        ],
        "data_links": ["https://www.nature.com/articles/s41746-020-00323-1"],
        "recommended_baselines": ["centralized", "FedAvg"],
    },
    # —— 交叉领域：智慧交通 ——
    {
        "id": "liu2020fedtraffic",
        "title": "Privacy-Preserving Traffic Flow Prediction: A Federated Learning Approach",
        "year": 2020,
        "venue": "IEEE IoT / ITS line",
        "external_id": "applied:fed-traffic-flow-2020",
        "setting": "hfl",
        "domain": "smart_transport",
        "facts": [
            {
                "fact_id": "fl_seed_traffic_1",
                "claim": "交通流预测可将路段/路口传感器划分为客户端做横向联邦，避免把原始车流量时序汇入单一中心。",
                "method": "FedAvg / FedGRU traffic prediction",
                "setting": "hfl",
                "domain": "smart_transport",
                "metrics": ["MAE", "RMSE", "MAPE", "communication_rounds"],
                "dataset": "PeMS / city loop detectors",
                "limitations": "时空相关使客户端并非独立；需报告高峰/平峰分段误差。",
                "source": "federated traffic flow prediction literature",
                "quote": "traffic flow prediction",
                "relevance": 0.9,
            },
            {
                "fact_id": "fl_seed_traffic_2",
                "claim": "智慧交通联邦设定下，通信轮次与边缘算力约束往往比精度更关键，报告应同时给出误差与通信成本。",
                "method": "edge FL for ITS",
                "setting": "hfl",
                "domain": "smart_transport",
                "metrics": ["communication_cost_mb", "MAE"],
                "dataset": "edge roadside units",
                "limitations": "仿真路网与真实城市拓扑差异大。",
                "source": "federated traffic flow prediction literature",
                "quote": "edge",
                "relevance": 0.86,
            },
        ],
        "data_links": [],
        "recommended_baselines": ["centralized GRU/LSTM", "FedAvg", "local-only"],
    },
    {
        "id": "its_fl_survey",
        "title": "Federated Learning for Intelligent Transportation Systems: Opportunities and Challenges",
        "year": 2022,
        "venue": "survey",
        "external_id": "survey:fl-its-2022",
        "setting": "both",
        "domain": "smart_transport",
        "facts": [
            {
                "fact_id": "fl_seed_its_1",
                "claim": "智能交通系统（ITS）中的联邦学习覆盖流量预测、轨迹挖掘、车路协同感知等，需处理高动态拓扑与严格时延。",
                "method": "FL for ITS survey",
                "setting": "both",
                "domain": "smart_transport",
                "metrics": ["latency_ms", "MAE", "communication_rounds"],
                "dataset": "V2X / detector / trajectory",
                "limitations": "场景碎片化，假设必须限定单一任务与数据模态。",
                "source": "ITS FL survey literature",
                "quote": "intelligent transportation",
                "relevance": 0.88,
            },
            {
                "fact_id": "fl_seed_its_2",
                "claim": "车企与交管分别持有车辆侧特征与路网标签时，可用垂直联邦验证跨组织协作，但实体对齐（车辆ID/时空键）是可行性前提。",
                "method": "VFL for V2X collaboration",
                "setting": "vfl",
                "domain": "smart_transport",
                "metrics": ["aligned_sample_rate", "AUC", "privacy_budget"],
                "dataset": "OEM features + traffic authority labels",
                "limitations": "ID 脱敏与对齐冲突是常见阻断。",
                "source": "ITS FL survey literature",
                "quote": "V2X",
                "relevance": 0.85,
            },
        ],
        "data_links": [],
        "recommended_baselines": ["FedAvg", "SplitNN", "centralized"],
    },
    {
        "id": "elbir2022v2xfl",
        "title": "Federated Learning for Vehicular Networks and Intelligent Transportation",
        "year": 2022,
        "venue": "communications / V2X line",
        "external_id": "applied:v2x-fl-2022",
        "setting": "hfl",
        "domain": "smart_transport",
        "facts": [
            {
                "fact_id": "fl_seed_v2x_1",
                "claim": "车联网联邦学习需显式建模车辆移动导致的客户端间歇在线与部分参与，否则通信轮次统计不可比。",
                "method": "FL with intermittent clients",
                "setting": "hfl",
                "domain": "smart_transport",
                "metrics": ["participation_rate", "global_accuracy", "communication_rounds"],
                "dataset": "vehicular network traces",
                "limitations": "仿真参与率与真实道路密度相关。",
                "source": "vehicular FL literature",
                "quote": "vehicular networks",
                "relevance": 0.84,
            }
        ],
        "data_links": [],
        "recommended_baselines": ["FedAvg", "FedProx"],
    },
    # —— 经典应用：金融风控 ——
    {
        "id": "yang2019flfinance",
        "title": "Federated Machine Learning: Concept and Applications (finance / enterprise FL)",
        "year": 2019,
        "venue": "ACM TIST",
        "external_id": "doi:10.1145/3298981",
        "setting": "both",
        "domain": "finance_risk",
        "facts": [
            {
                "fact_id": "fl_seed_fin_1",
                "claim": "金融风控联邦学习允许多家银行/机构在不共享原始客户数据的前提下联合建模，典型任务包括反欺诈与信用评分。",
                "method": "enterprise FL / HFL+VFL",
                "setting": "both",
                "domain": "finance_risk",
                "metrics": ["auc", "ks", "f1_score", "privacy_budget"],
                "dataset": "multi-bank credit / fraud features",
                "limitations": "监管合规与特征定义不一致常比算法更关键。",
                "source": "Yang et al., 2019 + finance FL practice",
                "quote": "credit scoring",
                "relevance": 0.92,
            },
            {
                "fact_id": "fl_seed_fin_2",
                "claim": "跨机构风控常采用垂直联邦：一方持有标签（违约/欺诈），另一方持有补充特征，实体对齐是可行性前提。",
                "method": "VFL credit risk",
                "setting": "vfl",
                "domain": "finance_risk",
                "metrics": ["aligned_sample_rate", "auc", "communication_cost_mb"],
                "dataset": "feature-party + label-party tabular",
                "limitations": "对齐键脱敏与样本交集不足会直接压低可用样本量。",
                "source": "finance VFL practice",
                "quote": "entity alignment",
                "relevance": 0.9,
            },
            {
                "fact_id": "fl_seed_fin_3",
                "claim": "金融联邦实验应同时报告业务指标（AUC/KS）与隐私/通信约束，避免只追中心化精度。",
                "method": "finance FL evaluation",
                "setting": "both",
                "domain": "finance_risk",
                "metrics": ["auc", "ks", "communication_rounds", "privacy_budget"],
                "dataset": "synthetic or partitioned credit tables",
                "limitations": "公开数据难还原真实跨行分布。",
                "source": "finance FL evaluation practice",
                "quote": "fraud detection",
                "relevance": 0.86,
            },
        ],
        "data_links": [],
        "recommended_baselines": ["centralized logistic", "FedAvg", "SplitNN/VFL"],
    },
    # —— 经典应用：智能终端与边缘 ——
    {
        "id": "hard2018nextword",
        "title": "Federated Learning for Mobile Keyboard Prediction",
        "year": 2018,
        "venue": "arXiv / applied",
        "external_id": "arXiv:1811.03604",
        "setting": "hfl",
        "domain": "edge_mobile",
        "facts": [
            {
                "fact_id": "fl_seed_edge_1",
                "claim": "手机输入法下一词预测是联邦学习在智能终端上的经典落地：本地训练、仅上传模型更新，兼顾个性化与隐私。",
                "method": "FedAvg on-device language model",
                "setting": "hfl",
                "domain": "edge_mobile",
                "metrics": ["top1_accuracy", "communication_rounds", "participation_rate"],
                "dataset": "on-device typing / CIFAR-like mobile shards",
                "limitations": "设备算力与间歇在线导致部分参与。",
                "source": "Hard et al., 2018",
                "quote": "keyboard prediction",
                "relevance": 0.93,
            },
            {
                "fact_id": "fl_seed_edge_2",
                "claim": "语音助手与推荐系统等边缘场景同样适合「本地更新 + 中心聚合」，报告需写明设备侧资源上限与通信预算。",
                "method": "on-device FL",
                "setting": "hfl",
                "domain": "edge_mobile",
                "metrics": ["communication_cost_mb", "latency_ms", "global_accuracy"],
                "dataset": "edge device shards",
                "limitations": "仿真设备数远小于真实亿级终端。",
                "source": "mobile FL practice",
                "quote": "on-device",
                "relevance": 0.88,
            },
        ],
        "data_links": ["https://arxiv.org/abs/1811.03604"],
        "recommended_baselines": ["centralized", "FedAvg", "local-only"],
    },
    {
        "id": "lim2020edgefl",
        "title": "Federated Learning in Mobile Edge Networks: A Comprehensive Survey",
        "year": 2020,
        "venue": "IEEE Commun. Surveys",
        "external_id": "survey:edge-fl-2020",
        "setting": "hfl",
        "domain": "edge_mobile",
        "facts": [
            {
                "fact_id": "fl_seed_edge_survey_1",
                "claim": "移动边缘网络中的联邦学习需联合优化模型精度、通信时延与能耗，是边缘计算与 FL 交叉的核心议题。",
                "method": "edge FL survey",
                "setting": "hfl",
                "domain": "edge_mobile",
                "metrics": ["latency_ms", "energy", "global_accuracy", "communication_rounds"],
                "dataset": "edge network traces",
                "limitations": "综述需落到可验证的单机小样假设。",
                "source": "Lim et al., 2020",
                "quote": "mobile edge",
                "relevance": 0.87,
            }
        ],
        "data_links": [],
        "recommended_baselines": ["FedAvg", "FedProx"],
    },
    # —— 经典应用：物联网与工业互联网 ——
    {
        "id": "iot_industrial_fl",
        "title": "Federated Learning for IoT and Industrial Predictive Maintenance",
        "year": 2021,
        "venue": "applied / survey line",
        "external_id": "applied:iot-industrial-fl",
        "setting": "hfl",
        "domain": "iot_industrial",
        "facts": [
            {
                "fact_id": "fl_seed_iot_1",
                "claim": "工业物联网中，工厂设备或传感器可分布式训练预测性维护与能耗优化模型，避免敏感工艺数据集中上传。",
                "method": "FedAvg on sensor time-series",
                "setting": "hfl",
                "domain": "iot_industrial",
                "metrics": ["f1_score", "mae", "communication_rounds", "participation_rate"],
                "dataset": "multi-factory sensor / CMAPSS-style",
                "limitations": "工况漂移与传感器标定差异造成强烈 Non-IID。",
                "source": "industrial IoT FL practice",
                "quote": "predictive maintenance",
                "relevance": 0.91,
            },
            {
                "fact_id": "fl_seed_iot_2",
                "claim": "工业联邦实验应按产线/设备划分客户端，并报告故障少数类召回，不能只用总体准确率。",
                "method": "IIoT FL evaluation",
                "setting": "hfl",
                "domain": "iot_industrial",
                "metrics": ["recall", "f1_score", "non_iid_degree"],
                "dataset": "imbalanced fault logs",
                "limitations": "真实故障样本稀少，合成标签需声明。",
                "source": "industrial IoT FL practice",
                "quote": "energy optimization",
                "relevance": 0.86,
            },
        ],
        "data_links": [],
        "recommended_baselines": ["local LSTM", "FedAvg", "FedProx"],
    },
    # —— 交叉：差分隐私 / 安全多方计算 ——
    {
        "id": "abadi2016dpsgd",
        "title": "Deep Learning with Differential Privacy",
        "year": 2016,
        "venue": "CCS",
        "external_id": "arXiv:1607.00133",
        "setting": "hfl",
        "domain": "privacy_crypto",
        "facts": [
            {
                "fact_id": "fl_seed_dp_1",
                "claim": "差分隐私（如 DP-SGD）可在联邦参数交互中加入噪声，提供可量化隐私预算 ε，增强理论隐私保障。",
                "method": "DP-SGD / DP-FedAvg",
                "setting": "hfl",
                "domain": "privacy_crypto",
                "metrics": ["privacy_budget", "global_accuracy", "communication_rounds"],
                "dataset": "MNIST / tabular classification",
                "limitations": "噪声增大通常牺牲精度；ε 选取需可辩护。",
                "source": "Abadi et al., 2016",
                "quote": "differential privacy",
                "relevance": 0.94,
            },
            {
                "fact_id": "fl_seed_dp_2",
                "claim": "联邦+差分隐私实验必须同时报告效用指标与隐私预算，并说明裁剪范数与噪声倍率等关键超参。",
                "method": "DP-FL evaluation",
                "setting": "hfl",
                "domain": "privacy_crypto",
                "metrics": ["privacy_budget", "global_accuracy"],
                "dataset": "FL classification",
                "limitations": "小样噪声方差大，结论外推需谨慎。",
                "source": "DP-FL practice",
                "quote": "privacy budget",
                "relevance": 0.89,
            },
        ],
        "data_links": ["https://arxiv.org/abs/1607.00133"],
        "recommended_baselines": ["FedAvg", "DP-FedAvg"],
    },
    {
        "id": "bonawitz2017secureagg",
        "title": "Practical Secure Aggregation for Privacy-Preserving Machine Learning",
        "year": 2017,
        "venue": "CCS",
        "external_id": "arXiv:1611.04482",
        "setting": "hfl",
        "domain": "privacy_crypto",
        "facts": [
            {
                "fact_id": "fl_seed_smc_1",
                "claim": "安全聚合（Secure Aggregation）用加密协议在服务器不可见单客户端更新的前提下完成求和，是联邦学习与安全多方计算结合的经典路径。",
                "method": "Secure Aggregation",
                "setting": "hfl",
                "domain": "privacy_crypto",
                "metrics": ["communication_cost_mb", "participation_rate", "global_accuracy"],
                "dataset": "on-device FL",
                "limitations": "掉线客户端与协议轮次增加系统复杂度。",
                "source": "Bonawitz et al., 2017",
                "quote": "secure aggregation",
                "relevance": 0.93,
            },
            {
                "fact_id": "fl_seed_smc_2",
                "claim": "报告联邦隐私增强方案时，应区分「本地数据不出域」「安全聚合」「差分隐私」三层保障，避免混为一谈。",
                "method": "privacy stack taxonomy",
                "setting": "both",
                "domain": "privacy_crypto",
                "metrics": ["privacy_budget", "communication_cost_mb"],
                "dataset": "n/a",
                "limitations": "本 Pack 不做真实 MPC runtime，仅提供写作与指标约束。",
                "source": "secure aggregation + DP practice",
                "quote": "MPC",
                "relevance": 0.88,
            },
        ],
        "data_links": ["https://arxiv.org/abs/1611.04482"],
        "recommended_baselines": ["plain FedAvg", "SecureAgg"],
    },
    # —— 交叉：计算机视觉 ——
    {
        "id": "fl_cv_detection",
        "title": "Federated Learning for Computer Vision: Multi-Camera Detection and Recognition",
        "year": 2021,
        "venue": "applied CV+FL",
        "external_id": "applied:fl-cv-2021",
        "setting": "hfl",
        "domain": "fl_cv",
        "facts": [
            {
                "fact_id": "fl_seed_cv_1",
                "claim": "多摄像头、多终端可用联邦学习联合训练目标检测/人脸识别等视觉模型，减少原始图像集中汇聚带来的泄露风险。",
                "method": "FedAvg on detection/classification CNN",
                "setting": "hfl",
                "domain": "fl_cv",
                "metrics": ["mAP", "global_accuracy", "communication_cost_mb"],
                "dataset": "multi-camera / CIFAR / domain-partitioned ImageNet subset",
                "limitations": "视觉模型通信载荷大，小样宜用浅网或合成分区。",
                "source": "CV federated learning practice",
                "quote": "object detection",
                "relevance": 0.9,
            },
            {
                "fact_id": "fl_seed_cv_2",
                "claim": "联邦视觉实验需报告域偏移（光照、机位、分辨率）导致的客户端漂移，并优先用自然摄像头划分而非随机切图。",
                "method": "domain-partitioned FL-CV",
                "setting": "hfl",
                "domain": "fl_cv",
                "metrics": ["client_drift", "mAP", "non_iid_degree"],
                "dataset": "camera-id partitioned images",
                "limitations": "人脸识别涉及更高合规门槛，课题需明确伦理边界。",
                "source": "CV federated learning practice",
                "quote": "multi-camera",
                "relevance": 0.87,
            },
        ],
        "data_links": [],
        "recommended_baselines": ["centralized CNN", "FedAvg", "FedProx"],
    },
    # —— 交叉：自然语言处理 ——
    {
        "id": "fl_nlp_lm",
        "title": "Federated Learning for NLP: Language Models and Cross-Organization Text",
        "year": 2020,
        "venue": "applied NLP+FL",
        "external_id": "applied:fl-nlp-2020",
        "setting": "hfl",
        "domain": "fl_nlp",
        "facts": [
            {
                "fact_id": "fl_seed_nlp_1",
                "claim": "联邦 NLP 可在跨组织、跨设备场景训练对话系统、输入法预测与语言模型，兼顾语料隐私。",
                "method": "FedAvg / FedProx on LM",
                "setting": "hfl",
                "domain": "fl_nlp",
                "metrics": ["perplexity", "top1_accuracy", "communication_rounds"],
                "dataset": "LEAF Shakespeare / StackOverflow / private corpora shards",
                "limitations": "词表与领域术语异构会放大 Non-IID。",
                "source": "federated NLP practice",
                "quote": "language model",
                "relevance": 0.91,
            },
            {
                "fact_id": "fl_seed_nlp_2",
                "claim": "相对中心化 NLP，联邦设定应额外报告通信轮次与客户端文本域差异，避免只报困惑度。",
                "method": "FedNLP evaluation",
                "setting": "hfl",
                "domain": "fl_nlp",
                "metrics": ["perplexity", "communication_cost_mb", "client_drift"],
                "dataset": "multi-domain text",
                "limitations": "真实跨机构语料不可外发，公开基准仅为代理。",
                "source": "federated NLP practice",
                "quote": "dialogue",
                "relevance": 0.86,
            },
        ],
        "data_links": ["https://github.com/TalwalkarLab/leaf"],
        "recommended_baselines": ["centralized LM", "FedAvg", "local-only"],
    },
    # —— 交叉：区块链 ——
    {
        "id": "fl_blockchain",
        "title": "Blockchain-Enabled Federated Learning: Authentication, Audit and Incentives",
        "year": 2021,
        "venue": "survey / systems line",
        "external_id": "survey:fl-blockchain-2021",
        "setting": "hfl",
        "domain": "fl_blockchain",
        "facts": [
            {
                "fact_id": "fl_seed_chain_1",
                "claim": "区块链可用于联邦节点身份认证、参数聚合审计与激励机制，提升系统可信与可追溯性。",
                "method": "blockchain-FL architecture",
                "setting": "hfl",
                "domain": "fl_blockchain",
                "metrics": ["audit_coverage", "participation_rate", "global_accuracy"],
                "dataset": "permissioned chain + FL clients",
                "limitations": "链上吞吐与隐私冲突；本 Pack 不提供链上 runtime。",
                "source": "blockchain-FL survey literature",
                "quote": "incentive",
                "relevance": 0.85,
            },
            {
                "fact_id": "fl_seed_chain_2",
                "claim": "若课题强调「可审计聚合」，报告应区分链上存证对象（哈希/摘要 vs 明文参数）与链下训练过程。",
                "method": "on-chain audit design",
                "setting": "both",
                "domain": "fl_blockchain",
                "metrics": ["audit_coverage", "communication_cost_mb"],
                "dataset": "n/a",
                "limitations": "存证不等于差分隐私。",
                "source": "blockchain-FL practice",
                "quote": "audit",
                "relevance": 0.82,
            },
        ],
        "data_links": [],
        "recommended_baselines": ["FedAvg", "FedAvg+audit log"],
    },
    # —— 交叉：联邦强化学习 ——
    {
        "id": "fl_rl_agents",
        "title": "Federated Reinforcement Learning: Sharing Policies without Centralizing Trajectories",
        "year": 2021,
        "venue": "applied / survey line",
        "external_id": "applied:fed-rl-2021",
        "setting": "hfl",
        "domain": "fl_rl",
        "facts": [
            {
                "fact_id": "fl_seed_frl_1",
                "claim": "联邦强化学习中，多个智能体在本地与环境交互，仅共享策略或价值网络参数，适用于自动驾驶、机器人控制等分布式场景。",
                "method": "FedRL / policy averaging",
                "setting": "hfl",
                "domain": "fl_rl",
                "metrics": ["episode_return", "communication_rounds", "participation_rate"],
                "dataset": "multi-agent Gym / driving sim shards",
                "limitations": "环境动态与奖励稀疏使聚合不稳定。",
                "source": "federated RL literature",
                "quote": "policy",
                "relevance": 0.88,
            },
            {
                "fact_id": "fl_seed_frl_2",
                "claim": "FedRL 评测应报告回报曲线与通信轮次，并声明各客户端环境是否同构；异构环境等同于强化版 Non-IID。",
                "method": "FedRL evaluation",
                "setting": "hfl",
                "domain": "fl_rl",
                "metrics": ["episode_return", "client_drift"],
                "dataset": "heterogeneous simulators",
                "limitations": "真实车/机器人实验成本高，小样多为仿真。",
                "source": "federated RL literature",
                "quote": "autonomous driving",
                "relevance": 0.84,
            },
        ],
        "data_links": [],
        "recommended_baselines": ["independent RL", "FedAvg on policies"],
    },
    # —— 交叉：持续 / 增量学习 ——
    {
        "id": "fl_continual",
        "title": "Federated Continual Learning under Non-IID Data and Concept Drift",
        "year": 2022,
        "venue": "applied / survey line",
        "external_id": "applied:fed-continual-2022",
        "setting": "hfl",
        "domain": "fl_continual",
        "facts": [
            {
                "fact_id": "fl_seed_cl_1",
                "claim": "联邦持续/增量学习在分布式场景应对 Non-IID 与概念漂移，目标是跨轮次稳定更新而不灾难性遗忘。",
                "method": "FedContinual / replay or regularization",
                "setting": "hfl",
                "domain": "fl_continual",
                "metrics": ["forgetting_measure", "global_accuracy", "communication_rounds"],
                "dataset": "class-incremental partitioned streams",
                "limitations": "客户端数据流不同步会使全局漂移难定义。",
                "source": "federated continual learning literature",
                "quote": "concept drift",
                "relevance": 0.9,
            },
            {
                "fact_id": "fl_seed_cl_2",
                "claim": "报告联邦增量学习时，应给出任务序列、遗忘度量与新任务精度，避免只报最终一轮全局准确率。",
                "method": "continual FL evaluation",
                "setting": "hfl",
                "domain": "fl_continual",
                "metrics": ["forgetting_measure", "average_accuracy"],
                "dataset": "streaming Non-IID",
                "limitations": "公开流式联邦基准仍有限。",
                "source": "federated continual learning literature",
                "quote": "catastrophic forgetting",
                "relevance": 0.87,
            },
        ],
        "data_links": [],
        "recommended_baselines": ["FedAvg", "FedProx", "EWC-style regularized FL"],
    },
    # —— 医疗健康补充（经典应用表述对齐）——
    {
        "id": "fl_health_imaging",
        "title": "Multi-Hospital Federated Learning for Disease Prediction and Medical Imaging",
        "year": 2021,
        "venue": "applied health FL",
        "external_id": "applied:multi-hospital-fl",
        "setting": "both",
        "domain": "smart_care",
        "facts": [
            {
                "fact_id": "fl_seed_hosp_1",
                "claim": "医院之间可用联邦学习协同训练疾病预测与医学影像分析模型，在保护患者隐私的同时缓解单中心数据不足。",
                "method": "multi-site FedAvg / SplitNN",
                "setting": "both",
                "domain": "smart_care",
                "metrics": ["auc", "dice", "privacy_budget", "communication_rounds"],
                "dataset": "multi-hospital EHR / imaging",
                "limitations": "标注协议与设备厂商差异导致特征分布偏移。",
                "source": "multi-hospital FL practice",
                "quote": "medical imaging",
                "relevance": 0.92,
            }
        ],
        "data_links": [],
        "recommended_baselines": ["centralized", "FedAvg", "SplitNN"],
    },
    # —— 交叉：联邦学习 + 多语言 ——
    {
        "id": "fl_multilingual_xlm",
        "title": "Federated Multilingual Learning: Cross-Lingual Transfer without Centralizing Corpora",
        "year": 2022,
        "venue": "applied / multilingual FL",
        "external_id": "applied:fl-multilingual-2022",
        "setting": "hfl",
        "domain": "fl_multilingual",
        "facts": [
            {
                "fact_id": "fl_seed_multi_1",
                "claim": "联邦多语言学习允许各机构/地区客户端用本地语种语料训练，仅聚合模型或适配器参数，避免集中上传敏感多语文本。",
                "method": "FedAvg / FedProx on multilingual encoder",
                "setting": "hfl",
                "domain": "fl_multilingual",
                "metrics": ["avg_lang_accuracy", "per_language_f1", "communication_rounds"],
                "dataset": "XNLID / multi-lang instruction shards by language",
                "limitations": "低资源语种客户端样本少，全局模型易偏向高资源语。",
                "source": "federated multilingual practice",
                "quote": "cross-lingual",
                "relevance": 0.91,
            },
            {
                "fact_id": "fl_seed_multi_2",
                "claim": "多语言联邦评测必须按语种分别报告指标，并写明客户端按语种/地区划分方式，不能只报宏平均。",
                "method": "per-language FL evaluation",
                "setting": "hfl",
                "domain": "fl_multilingual",
                "metrics": ["per_language_f1", "macro_f1", "client_drift"],
                "dataset": "language-partitioned corpora",
                "limitations": "脚本语言与分词器差异会引入额外异构。",
                "source": "federated multilingual practice",
                "quote": "low-resource",
                "relevance": 0.88,
            },
            {
                "fact_id": "fl_seed_multi_3",
                "claim": "当客户端语种分布极度不均时，可采用语种感知聚合权重或适配器路由，减轻高资源语对低资源语的压制。",
                "method": "language-aware aggregation",
                "setting": "hfl",
                "domain": "fl_multilingual",
                "metrics": ["per_language_f1", "participation_rate"],
                "dataset": "imbalanced multilingual shards",
                "limitations": "加权策略需防泄露客户端语种规模元数据时的隐私权衡。",
                "source": "federated multilingual practice",
                "quote": "language imbalance",
                "relevance": 0.85,
            },
        ],
        "data_links": [],
        "recommended_baselines": ["centralized multilingual", "FedAvg", "language-local only"],
    },
    # —— 交叉：联邦学习 + 客户端 LoRA 异构 ——
    {
        "id": "fl_hetero_lora",
        "title": "Federated Learning with Heterogeneous Client LoRA Adapters",
        "year": 2024,
        "venue": "applied FedPEFT / hetero-LoRA",
        "external_id": "applied:fl-hetero-lora-2024",
        "setting": "hfl",
        "domain": "fl_lora_hetero",
        "facts": [
            {
                "fact_id": "fl_seed_hetlora_1",
                "claim": "客户端模型 LoRA 异构指各客户端可采用不同秩 r、目标模块或适配器结构，以匹配本地算力与数据规模，而非强制统一全参或统一 LoRA 配置。",
                "method": "heterogeneous FedLoRA",
                "setting": "hfl",
                "domain": "fl_lora_hetero",
                "metrics": ["trainable_params", "downstream_accuracy", "communication_cost_mb"],
                "dataset": "multi-client instruction / domain shards",
                "limitations": "异构适配器不能直接朴素平均，需对齐或投影聚合。",
                "source": "heterogeneous FedLoRA practice",
                "quote": "heterogeneous LoRA",
                "relevance": 0.93,
            },
            {
                "fact_id": "fl_seed_hetlora_2",
                "claim": "LoRA 秩与放置层异构时，聚合应基于共享子空间投影、层对齐或服务器侧公共适配器，并报告各客户端 (r, target_modules) 配置表。",
                "method": "LoRA alignment / subspace aggregation",
                "setting": "hfl",
                "domain": "fl_lora_hetero",
                "metrics": ["adapter_align_rate", "global_accuracy", "communication_rounds"],
                "dataset": "hetero-rank client adapters",
                "limitations": "错误对齐会导致负迁移；小样需固定随机种子复现。",
                "source": "heterogeneous FedLoRA practice",
                "quote": "rank heterogeneity",
                "relevance": 0.9,
            },
            {
                "fact_id": "fl_seed_hetlora_3",
                "claim": "相对同构 FedLoRA，异构设定的核心可证伪点是：在通信预算相近时，允许客户端差异化 LoRA 能否提升弱客户端下游精度且不明显损害强客户端。",
                "method": "hetero vs homo FedLoRA comparison",
                "setting": "hfl",
                "domain": "fl_lora_hetero",
                "metrics": ["weak_client_accuracy", "strong_client_accuracy", "communication_cost_mb"],
                "dataset": "capacity-skewed clients",
                "limitations": "真实 GPU 异构难在本地 Pack 完整复现，可用合成秩表代理。",
                "source": "heterogeneous FedLoRA practice",
                "quote": "client capacity",
                "relevance": 0.88,
            },
        ],
        "data_links": [],
        "recommended_baselines": ["homogeneous FedLoRA", "local-only LoRA", "full-param FedAvg"],
    },
]


DATASETS = {
    "leaf_femnist.yaml": """id: leaf_femnist
name: LEAF FEMNIST
setting: hfl
download_url: https://github.com/TalwalkarLab/leaf
license: research
citation: Caldas et al., LEAF, 2018
partition:
  num_clients: 3550
  non_iid_type: writer_natural
  note: 按书写者自然划分；小样可用 scripts 合成子集
schema:
  - client_id
  - sample_id
  - label
  - feature_vector
pilot_subset:
  max_clients: 10
  max_samples_per_client: 50
upload_requirement: optional
description: 手写字符联邦基准，适合 FedAvg / Non-IID 小样
""",
    "leaf_shakespeare.yaml": """id: leaf_shakespeare
name: LEAF Shakespeare
setting: hfl
download_url: https://github.com/TalwalkarLab/leaf
license: research
citation: Caldas et al., LEAF, 2018
partition:
  num_clients: 1129
  non_iid_type: role_natural
schema:
  - client_id
  - text_snippet
  - next_char
pilot_subset:
  max_clients: 8
  max_samples_per_client: 100
upload_requirement: optional
description: 角色级文本下一字符预测，适合通信轮次对比
""",
    "synthetic_hfl_noniid.yaml": """id: synthetic_hfl_noniid
name: Synthetic HFL Non-IID Tabular
setting: hfl
download_url: local://scripts/hfl_non_iid_partition.py
license: generated
citation: AISci FL Starter Pack
partition:
  num_clients: 5
  non_iid_type: label_skew
  non_iid_degree: 0.8
schema:
  - client_id
  - sample_id
  - x1
  - x2
  - x3
  - label
pilot_subset:
  max_rows: 500
upload_requirement: optional
description: 由脚本生成的标签偏斜表格，无需下载 LEAF 全量
""",
    "synthetic_vfl_two_party.yaml": """id: synthetic_vfl_two_party
name: Synthetic Two-Party VFL
setting: vfl
download_url: local://scripts/vfl_aligned_logistic_pilot.py
license: generated
citation: AISci FL Starter Pack
partition:
  parties: [feature_party_a, label_party]
  alignment_key: entity_id
schema:
  - entity_id
  - party_id
  - feat_a1
  - feat_a2
  - label
pilot_subset:
  max_entities: 300
  target_alignment_rate: 0.9
upload_requirement: optional
description: 两方垂直联邦合成表，用于对齐率与 logistic pilot
""",
    "uci_adult_vfl_split.yaml": """id: uci_adult_vfl_split
name: UCI Adult (VFL feature split recipe)
setting: vfl
download_url: https://archive.ics.uci.edu/dataset/2/adult
license: UCI
citation: UCI Adult
partition:
  parties: [demographics, employment]
  alignment_key: entity_id
schema:
  - entity_id
  - age
  - education
  - occupation
  - hours_per_week
  - income_label
pilot_subset:
  max_rows: 1000
upload_requirement: optional
description: 公开表格按列切分为 VFL 特征方；需自行加 entity_id 对齐
""",
    "hf_fl_search.yaml": """id: hf_fl_search
name: HuggingFace Federated Learning Search
setting: both
download_url: https://huggingface.co/datasets?search=federated+learning
license: varies
citation: HuggingFace Hub
partition:
  note: 检索入口，具体划分视数据集而定
schema:
  - client_id
  - label
pilot_subset:
  max_rows: 500
upload_requirement: optional
description: 公开联邦/分区数据检索入口
""",
    "synthetic_llm_peft_shards.yaml": """id: synthetic_llm_peft_shards
name: Synthetic Multi-Client Instruction Shards (FedPEFT pilot)
setting: hfl
domain: llm_ft
download_url: local://generated
license: generated
citation: AISci FL Starter Pack
partition:
  num_clients: 4
  non_iid_type: instruction_domain_skew
  note: 合成指令分片，模拟跨机构域差异；真实 LLM 权重不下发
schema:
  - client_id
  - instruction_id
  - domain_tag
  - prompt
  - response
pilot_subset:
  max_clients: 4
  max_samples_per_client: 50
upload_requirement: optional
description: 联邦大模型/LoRA 微调小样用合成指令分片元数据
""",
    "sisfall_har_fl.yaml": """id: sisfall_har_fl
name: SisFall / HAR Federated Recipe
setting: hfl
domain: smart_care
download_url: https://sistemic.udea.edu.co/en/research/projects/english-falls/
license: research
citation: SisFall dataset
partition:
  num_clients: subject_or_device
  non_iid_type: subject_natural
  note: 按受试者/设备划分客户端；跌倒为少数类
schema:
  - client_id
  - sample_id
  - accel_x
  - accel_y
  - accel_z
  - label
pilot_subset:
  max_clients: 8
  max_samples_per_client: 100
upload_requirement: optional
description: 智慧康养跌倒/活动识别联邦划分配方（需自行下载公开 HAR）
""",
    "pems_traffic_fl.yaml": """id: pems_traffic_fl
name: PeMS-style Traffic Flow Federated Recipe
setting: hfl
domain: smart_transport
download_url: https://pems.dot.ca.gov/
license: research
citation: Caltrans PeMS
partition:
  num_clients: roadside_unit_or_segment
  non_iid_type: spatial_skew
  note: 按路段/检测器划分客户端；关注高峰时段误差
schema:
  - client_id
  - timestamp
  - flow
  - occupancy
  - speed
pilot_subset:
  max_clients: 10
  max_timesteps: 500
upload_requirement: optional
description: 智慧交通流量预测联邦划分配方（公开路网流量入口）
""",
    "vfl_care_sensor_label.yaml": """id: vfl_care_sensor_label
name: Synthetic Care VFL (sensor party + label party)
setting: vfl
domain: smart_care
download_url: local://scripts/vfl_aligned_logistic_pilot.py
license: generated
citation: AISci FL Starter Pack
partition:
  parties: [wearable_feature_party, care_label_party]
  alignment_key: session_id
schema:
  - session_id
  - party_id
  - feat_hr
  - feat_accel
  - fall_label
pilot_subset:
  max_entities: 300
  target_alignment_rate: 0.9
upload_requirement: optional
description: 康养垂直联邦：设备方特征 + 机构方跌倒/告警标签
""",
    "synthetic_finance_vfl.yaml": """id: synthetic_finance_vfl
name: Synthetic Finance VFL (feature bank + label bank)
setting: vfl
domain: finance_risk
download_url: local://scripts/vfl_aligned_logistic_pilot.py
license: generated
citation: AISci FL Starter Pack
partition:
  parties: [feature_bank, label_bank]
  alignment_key: customer_id
schema:
  - customer_id
  - party_id
  - feat_income
  - feat_history
  - default_label
pilot_subset:
  max_entities: 400
  target_alignment_rate: 0.9
upload_requirement: optional
description: 金融风控垂直联邦合成表（反欺诈/信用评分小样）
""",
    "leaf_shakespeare_nlp.yaml": """id: leaf_shakespeare_nlp
name: LEAF Shakespeare (FedNLP proxy)
setting: hfl
domain: fl_nlp
download_url: https://github.com/TalwalkarLab/leaf
license: research
citation: Caldas et al., LEAF, 2018
partition:
  num_clients: 1129
  non_iid_type: role_natural
schema:
  - client_id
  - text_snippet
  - next_char
pilot_subset:
  max_clients: 8
  max_samples_per_client: 100
upload_requirement: optional
description: 联邦 NLP / 输入法预测代理基准（角色级文本）
""",
    "synthetic_multilingual_shards.yaml": """id: synthetic_multilingual_shards
name: Synthetic Multilingual Client Shards
setting: hfl
domain: fl_multilingual
download_url: local://generated
license: generated
citation: AISci FL Starter Pack
partition:
  num_clients: 6
  non_iid_type: language_partition
  note: 按语种划分客户端；含高/低资源语不平衡
schema:
  - client_id
  - language_code
  - sample_id
  - text
  - label
pilot_subset:
  max_clients: 6
  max_samples_per_client: 80
upload_requirement: optional
description: 联邦多语言小样：语种分区与低资源语压制场景
""",
    "synthetic_hetero_lora_configs.yaml": """id: synthetic_hetero_lora_configs
name: Synthetic Heterogeneous Client LoRA Config Table
setting: hfl
domain: fl_lora_hetero
download_url: local://generated
license: generated
citation: AISci FL Starter Pack
partition:
  num_clients: 5
  non_iid_type: capacity_and_rank_skew
  note: 客户端 r / target_modules / 算力档位异构，聚合需对齐
schema:
  - client_id
  - lora_rank
  - target_modules
  - device_tier
  - num_local_samples
pilot_subset:
  max_clients: 5
upload_requirement: optional
description: 客户端 LoRA 异构配置表（秩/模块/算力），供 FedLoRA 对齐实验写作
""",
}


# —— 实验范式（v1.4+）：默认标准 Non-IID = Dirichlet α=0.1 + FedAvg/FedProx ——
EXPERIMENT_PROFILES = {
    "standard_non_iid": {
        "id": "standard_non_iid",
        "label": "标准 Non-IID（Dirichlet + FedProx 对比）",
        "is_default": True,
        "setting": "hfl",
        "partition": {
            "id": "dirichlet_non_iid",
            "method": "dirichlet",
            "alpha": 0.1,
            "paired_baseline_partition": "iid_uniform",
            "num_clients": 20,
            "script": "scripts/hfl_dirichlet_partition.py",
        },
        "baselines": {
            "id": "hfl_noniid_ablation",
            "required": ["local_only", "centralized", "FedAvg", "FedProx"],
            "system_defaults": {
                "num_clients": 20,
                "participation_rate": 0.2,
                "local_epochs": 5,
                "batch_size": 32,
                "rounds": 30,
                "fedprox_mu": 0.01,
                "seed": 42,
            },
            "compare_script": "scripts/hfl_baseline_compare_pilot.py",
        },
        "metrics": {
            "id": "hfl_classification",
            "required": [
                "global_accuracy",
                "communication_rounds",
                "non_iid_type",
                "non_iid_degree",
                "client_drift",
                "partition_method",
            ],
            "optional": ["local_accuracy", "communication_cost_mb", "participation_rate"],
            "stability": "mean_std_over_seeds_recommended",
        },
        "report_must_include": [
            "partition_method=dirichlet 与 alpha",
            "IID 对照或说明为何省略",
            "Local / Centralized / FedAvg / FedProx 对比",
            "communication_rounds 与 client_drift",
            "声明单机模拟、非多机部署",
        ],
    },
    "quick_iid": {
        "id": "quick_iid",
        "label": "快速验证（IID + 三基线）",
        "is_default": False,
        "setting": "hfl",
        "partition": {
            "id": "iid_uniform",
            "method": "iid",
            "alpha": None,
            "num_clients": 10,
            "script": "scripts/hfl_non_iid_partition.py",
        },
        "baselines": {
            "id": "hfl_quick",
            "required": ["local_only", "centralized", "FedAvg"],
            "system_defaults": {
                "num_clients": 10,
                "participation_rate": 1.0,
                "local_epochs": 3,
                "batch_size": 32,
                "rounds": 10,
                "seed": 42,
            },
            "compare_script": "scripts/hfl_baseline_compare_pilot.py",
        },
        "metrics": {
            "id": "hfl_classification_lite",
            "required": ["global_accuracy", "communication_rounds", "partition_method"],
        },
        "report_must_include": ["IID 划分", "三基线对比", "通信轮次"],
    },
}

PARTITIONS_CATALOG = {
    "iid_uniform": {
        "id": "iid_uniform",
        "name": "IID 均匀划分",
        "control_variable": "data_heterogeneity",
        "description": "数据随机均匀打乱后分配，作为理想对照。",
        "params": {},
        "script": "scripts/hfl_non_iid_partition.py",
        "metrics_keys": ["partition_method", "global_accuracy"],
    },
    "dirichlet_non_iid": {
        "id": "dirichlet_non_iid",
        "name": "Dirichlet Non-IID",
        "control_variable": "data_heterogeneity",
        "description": "用 Dirichlet(α) 控制类别偏斜；α 越小越 Non-IID。默认 α=0.1。",
        "params": {"alpha": [0.1, 0.5, 1.0]},
        "script": "scripts/hfl_dirichlet_partition.py",
        "metrics_keys": ["partition_method", "non_iid_degree", "alpha", "client_drift"],
        "default_for_profile": "standard_non_iid",
    },
    "pathological_k_classes": {
        "id": "pathological_k_classes",
        "name": "Pathological Non-IID（每客户端 K 类）",
        "control_variable": "data_heterogeneity",
        "description": "每客户端仅少量类别，极端异构。",
        "params": {"classes_per_client": 2},
        "script": "scripts/hfl_dirichlet_partition.py",
        "metrics_keys": ["partition_method", "classes_per_client", "global_accuracy"],
    },
    "quantity_skew": {
        "id": "quantity_skew",
        "name": "数量偏斜",
        "control_variable": "sample_size_heterogeneity",
        "description": "客户端样本量差异大（Dirichlet 或长尾）。",
        "params": {"quantity_alpha": 0.5},
        "script": "scripts/hfl_dirichlet_partition.py",
        "metrics_keys": ["partition_method", "sample_size_cv"],
    },
    "natural_user_id": {
        "id": "natural_user_id",
        "name": "真实用户天然 Non-IID",
        "control_variable": "natural_heterogeneity",
        "description": "FEMNIST/Shakespeare 等按用户/角色划分。",
        "params": {},
        "datasets": ["leaf_femnist", "leaf_shakespeare", "leaf_shakespeare_nlp"],
        "metrics_keys": ["partition_method", "num_clients", "global_accuracy"],
    },
}

BASELINES_CATALOG = {
    "hfl_noniid_ablation": {
        "id": "hfl_noniid_ablation",
        "tiers": {
            "upper_bound": ["centralized"],
            "lower_bound": ["local_only"],
            "core": ["FedAvg"],
            "heterogeneity": ["FedProx"],
        },
        "fair_comparison_rules": [
            "固定 E、B、client 划分种子",
            "同一 Dirichlet 划分上对比 FedAvg 与 FedProx",
            "报告 communication_rounds 至收敛或固定 rounds",
        ],
    }
}

METRICS_CATALOG = {
    "hfl_classification": {
        "id": "hfl_classification",
        "performance": ["global_accuracy", "loss"],
        "efficiency": ["communication_rounds", "communication_cost_mb"],
        "robustness": ["client_drift", "non_iid_degree"],
        "partition_meta": ["partition_method", "alpha", "num_clients", "participation_rate"],
        "stability_note": "建议 ≥3 个随机种子报告 mean±std",
    },
    "vfl_tabular": {
        "id": "vfl_tabular",
        "performance": ["auc", "f1_score", "accuracy"],
        "efficiency": ["aligned_sample_rate", "communication_cost_mb"],
        "robustness": ["alignment_success_rate"],
        "partition_meta": ["alignment_key", "num_parties"],
    },
}


SCRIPTS_README = """# FL 参考脚本

纯本地可跑（numpy / sklearn），**无 Flower/FATE 依赖**。

| 脚本 | 场景 | 输出 |
|------|------|------|
| `hfl_fedavg_pilot.py` | HFL FedAvg | `metrics.json` |
| `hfl_non_iid_partition.py` | 生成 label-skew Non-IID CSV | `synthetic_hfl.csv` + metrics |
| `hfl_dirichlet_partition.py` | Dirichlet / pathological 划分 | CSV + metrics |
| `hfl_baseline_compare_pilot.py` | Local / Centralized / FedAvg / FedProx | `metrics.json` 对比表 |
| `vfl_aligned_logistic_pilot.py` | VFL 对齐+logistic | `metrics.json` |
| `run_fedavg_pilot.py` | 供服务调用的统一入口 | stdout JSON |

默认实验档位：**标准 Non-IID（Dirichlet α=0.1 + FedAvg/FedProx）**。
在迭代实验中：将脚本路径与注释中的成功标准复制到 `analysis_script`，按数据路径改参。
"""


HFL_FEDAVG = r'''#!/usr/bin/env python3
"""HFL FedAvg pilot (local simulation, no Flower).

适用边界: 表格二分类；客户端按 client_id 划分。
成功标准: global_accuracy 可复现；写出 communication_rounds。
常见失败: 客户端样本过少、标签全偏到一侧。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def _logistic_sgd(X, y, steps=20, lr=0.1):
    w = np.zeros(X.shape[1])
    b = 0.0
    for _ in range(steps):
        z = X @ w + b
        p = 1 / (1 + np.exp(-np.clip(z, -20, 20)))
        err = p - y
        w -= lr * (X.T @ err) / max(len(y), 1)
        b -= lr * float(np.mean(err))
    return w, b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="", help="optional CSV with client_id, features, label")
    ap.add_argument("--clients", type=int, default=5)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--out", default="metrics.json")
    args = ap.parse_args()

    rng = np.random.default_rng(42)
    n = 200
    X = rng.normal(size=(n, 4))
    y = (X[:, 0] + 0.5 * X[:, 1] > 0).astype(float)
    client_ids = np.array([i % args.clients for i in range(n)])

    gw = np.zeros(X.shape[1])
    gb = 0.0
    hist = []
    for r in range(args.rounds):
        ws, bs, ns = [], [], []
        for c in range(args.clients):
            mask = client_ids == c
            if not np.any(mask):
                continue
            w, b = _logistic_sgd(X[mask], y[mask], steps=10)
            # one local step toward global init mix
            w = 0.5 * w + 0.5 * gw
            b = 0.5 * b + 0.5 * gb
            ws.append(w)
            bs.append(b)
            ns.append(int(mask.sum()))
        tot = sum(ns) or 1
        gw = sum(w * n for w, n in zip(ws, ns)) / tot
        gb = sum(b * n for b, n in zip(bs, ns)) / tot
        pred = (X @ gw + gb > 0).astype(float)
        acc = float(np.mean(pred == y))
        hist.append({"round": r + 1, "global_accuracy": acc})

    metrics = {
        "primary_metric": hist[-1]["global_accuracy"] if hist else 0.0,
        "global_accuracy": hist[-1]["global_accuracy"] if hist else 0.0,
        "communication_rounds": args.rounds,
        "num_clients": args.clients,
        "method": "FedAvg",
        "history": hist,
        "note": "local HFL pilot; not multi-machine FL",
    }
    Path(args.out).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
'''

HFL_NONIID = r'''#!/usr/bin/env python3
"""Generate synthetic HFL Non-IID tabular CSV + quick metrics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clients", type=int, default=5)
    ap.add_argument("--rows", type=int, default=400)
    ap.add_argument("--skew", type=float, default=0.8)
    ap.add_argument("--out_csv", default="synthetic_hfl.csv")
    ap.add_argument("--out_metrics", default="metrics.json")
    args = ap.parse_args()

    rng = np.random.default_rng(0)
    rows = []
    for i in range(args.rows):
        c = i % args.clients
        # label skew: client prefers its own label
        if rng.random() < args.skew:
            label = c % 2
        else:
            label = int(rng.integers(0, 2))
        x = rng.normal(loc=label, size=3)
        rows.append(
            {
                "client_id": f"c{c}",
                "sample_id": f"s{i}",
                "x1": float(x[0]),
                "x2": float(x[1]),
                "x3": float(x[2]),
                "label": int(label),
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(args.out_csv, index=False)
    metrics = {
        "num_clients": args.clients,
        "rows": len(df),
        "non_iid_type": "label_skew",
        "non_iid_degree": args.skew,
        "primary_metric": float(df["label"].mean()),
        "note": "partition helper for HFL pilots",
    }
    Path(args.out_metrics).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
'''

VFL_PILOT = r'''#!/usr/bin/env python3
"""Two-party VFL-style aligned logistic pilot (local simulation).

成功标准: alignment_success_rate >= 0.85 且写出 party AUC/acc。
常见失败: entity_id 不对齐、标签方缺失。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entities", type=int, default=300)
    ap.add_argument("--drop_rate", type=float, default=0.1, help="simulate misalignment")
    ap.add_argument("--out", default="metrics.json")
    args = ap.parse_args()

    rng = np.random.default_rng(1)
    n = args.entities
    entity = np.arange(n)
    keep = rng.random(n) > args.drop_rate
    aligned = entity[keep]
    xa = rng.normal(size=(len(aligned), 2))
    y = (xa[:, 0] + 0.3 * xa[:, 1] > 0).astype(float)

    # closed-form-ish logistic via least squares on sigmoid target approx
    X = np.column_stack([xa, np.ones(len(aligned))])
    # ridge
    beta = np.linalg.pinv(X.T @ X + 1e-2 * np.eye(3)) @ X.T @ y
    pred = (X @ beta > 0.5).astype(float)
    acc = float(np.mean(pred == y))
    rate = float(len(aligned) / max(n, 1))

    metrics = {
        "primary_metric": acc,
        "global_accuracy": acc,
        "aligned_sample_rate": rate,
        "alignment_success_rate": rate,
        "num_parties": 2,
        "method": "VFL-aligned-logistic",
        "alignment_key": "entity_id",
        "gate_threshold": 0.85,
        "gate_passed": rate >= 0.85,
        "note": "local VFL pilot; not multi-party deployment",
    }
    Path(args.out).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
'''

HFL_DIRICHLET = r'''#!/usr/bin/env python3
"""Dirichlet / pathological Non-IID partition for HFL pilots (local only).

默认档位: Dirichlet α=0.1，20 clients。
成功标准: 写出 partition_method / alpha / non_iid_degree 与 CSV。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _dirichlet_partition(y: np.ndarray, n_clients: int, alpha: float, rng: np.random.Generator):
    labels = np.unique(y)
    client_indices = [[] for _ in range(n_clients)]
    for lab in labels:
        idx = np.where(y == lab)[0]
        rng.shuffle(idx)
        props = rng.dirichlet([alpha] * n_clients)
        cuts = (np.cumsum(props) * len(idx)).astype(int)[:-1]
        splits = np.split(idx, cuts)
        for c, part in enumerate(splits):
            client_indices[c].extend(part.tolist())
    return client_indices


def _pathological_partition(y: np.ndarray, n_clients: int, k: int, rng: np.random.Generator):
    labels = list(np.unique(y))
    rng.shuffle(labels)
    client_indices = [[] for _ in range(n_clients)]
    for c in range(n_clients):
        labs = labels[(c * k) % len(labels) : (c * k) % len(labels) + k]
        if len(labs) < k:
            labs = (labels + labels)[:k]
        for lab in labs:
            idx = np.where(y == lab)[0]
            take = idx[rng.choice(len(idx), size=max(1, len(idx) // n_clients), replace=False)]
            client_indices[c].extend(take.tolist())
    return client_indices


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dirichlet", "pathological", "quantity"], default="dirichlet")
    ap.add_argument("--alpha", type=float, default=0.1)
    ap.add_argument("--clients", type=int, default=20)
    ap.add_argument("--rows", type=int, default=800)
    ap.add_argument("--n_classes", type=int, default=4)
    ap.add_argument("--classes_per_client", type=int, default=2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out_csv", default="synthetic_dirichlet_hfl.csv")
    ap.add_argument("--out_metrics", default="metrics.json")
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    X = rng.normal(size=(args.rows, 4))
    # synthetic multi-class labels correlated with first feature
    y = np.clip(((X[:, 0] + 2) * args.n_classes / 4).astype(int), 0, args.n_classes - 1)

    if args.mode == "pathological":
        parts = _pathological_partition(y, args.clients, args.classes_per_client, rng)
        partition_method = "pathological"
        non_iid_degree = 1.0
    else:
        parts = _dirichlet_partition(y, args.clients, args.alpha, rng)
        partition_method = "dirichlet"
        non_iid_degree = float(1.0 / max(args.alpha, 1e-6))

    # quantity skew: resample client sizes via Dirichlet
    if args.mode == "quantity":
        sizes = rng.dirichlet([args.alpha] * args.clients)
        sizes = (sizes * args.rows).astype(int)
        sizes[-1] = args.rows - sizes[:-1].sum()
        order = rng.permutation(args.rows)
        parts = []
        start = 0
        for s in sizes:
            parts.append(order[start : start + max(s, 0)].tolist())
            start += max(s, 0)
        partition_method = "quantity_skew"
        non_iid_degree = float(np.std([len(p) for p in parts]) / max(np.mean([len(p) for p in parts]), 1))

    rows = []
    for c, idxs in enumerate(parts):
        for i in idxs:
            rows.append(
                {
                    "client_id": f"c{c}",
                    "sample_id": f"s{i}",
                    "x1": float(X[i, 0]),
                    "x2": float(X[i, 1]),
                    "x3": float(X[i, 2]),
                    "x4": float(X[i, 3]),
                    "label": int(y[i]),
                }
            )
    df = pd.DataFrame(rows)
    if args.mode == "quantity":
        pass
    df.to_csv(args.out_csv, index=False)

    # crude client_drift: variance of per-client label means
    drifts = []
    for c in range(args.clients):
        sub = df[df["client_id"] == f"c{c}"]["label"]
        if len(sub):
            drifts.append(float(sub.mean()))
    client_drift = float(np.std(drifts)) if drifts else 0.0

    metrics = {
        "primary_metric": client_drift,
        "partition_method": partition_method,
        "non_iid_type": partition_method,
        "non_iid_degree": non_iid_degree,
        "alpha": args.alpha if partition_method == "dirichlet" else None,
        "num_clients": args.clients,
        "rows": len(df),
        "client_drift": client_drift,
        "classes_per_client": args.classes_per_client if partition_method == "pathological" else None,
        "seed": args.seed,
        "note": "partition helper for standard Non-IID FL pilots",
    }
    Path(args.out_metrics).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
'''

HFL_BASELINE_COMPARE = r'''#!/usr/bin/env python3
"""Compare Local / Centralized / FedAvg / FedProx on Dirichlet-partitioned tabular data.

默认档位: 标准 Non-IID（Dirichlet α=0.1）+ FedProx μ 对比。
成功标准: metrics.json 含 methods 对比表、partition_method、communication_rounds。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def _logistic_sgd(X, y, w=None, b=0.0, steps=20, lr=0.1, prox_mu=0.0, w_global=None, b_global=0.0):
    w = np.zeros(X.shape[1]) if w is None else w.copy()
    b = float(b)
    wg = w_global if w_global is not None else w
    for _ in range(steps):
        z = X @ w + b
        p = 1 / (1 + np.exp(-np.clip(z, -20, 20)))
        err = p - y
        grad_w = (X.T @ err) / max(len(y), 1) + prox_mu * (w - wg)
        grad_b = float(np.mean(err)) + prox_mu * (b - b_global)
        w -= lr * grad_w
        b -= lr * grad_b
    return w, b


def _acc(X, y, w, b):
    pred = (X @ w + b > 0).astype(float)
    return float(np.mean(pred == y))


def _make_dirichlet_data(n_clients, n_rows, alpha, seed, n_classes=2):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n_rows, 4))
    y = (X[:, 0] + 0.3 * X[:, 1] > 0).astype(float)
    # binary dirichlet by soft assignment via alpha-skewed client preference
    client_ids = np.zeros(n_rows, dtype=int)
    for lab in (0, 1):
        idx = np.where(y == lab)[0]
        rng.shuffle(idx)
        props = rng.dirichlet([alpha] * n_clients)
        cuts = (np.cumsum(props) * len(idx)).astype(int)[:-1]
        for c, part in enumerate(np.split(idx, cuts)):
            client_ids[part] = c
    return X, y, client_ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clients", type=int, default=20)
    ap.add_argument("--rows", type=int, default=800)
    ap.add_argument("--alpha", type=float, default=0.1)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--local_epochs", type=int, default=5)
    ap.add_argument("--participation", type=float, default=0.2)
    ap.add_argument("--mu", type=float, default=0.01, help="FedProx proximal coefficient")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="metrics.json")
    args = ap.parse_args()

    X, y, client_ids = _make_dirichlet_data(args.clients, args.rows, args.alpha, args.seed)
    rng = np.random.default_rng(args.seed)

    # Centralized
    w_c, b_c = _logistic_sgd(X, y, steps=args.local_epochs * 10)
    acc_central = _acc(X, y, w_c, b_c)

    # Local-only: average of per-client models evaluated globally
    local_accs = []
    for c in range(args.clients):
        mask = client_ids == c
        if not np.any(mask):
            continue
        w_l, b_l = _logistic_sgd(X[mask], y[mask], steps=args.local_epochs * 5)
        local_accs.append(_acc(X, y, w_l, b_l))
    acc_local = float(np.mean(local_accs)) if local_accs else 0.0

    def run_federated(prox_mu: float):
        gw = np.zeros(X.shape[1])
        gb = 0.0
        hist = []
        k = max(1, int(args.clients * args.participation))
        for r in range(args.rounds):
            chosen = rng.choice(args.clients, size=min(k, args.clients), replace=False)
            ws, bs, ns = [], [], []
            for c in chosen:
                mask = client_ids == c
                if not np.any(mask):
                    continue
                w, b = _logistic_sgd(
                    X[mask],
                    y[mask],
                    w=gw,
                    b=gb,
                    steps=args.local_epochs,
                    prox_mu=prox_mu,
                    w_global=gw,
                    b_global=gb,
                )
                ws.append(w)
                bs.append(b)
                ns.append(int(mask.sum()))
            if ws:
                tot = sum(ns) or 1
                gw = sum(w * n for w, n in zip(ws, ns)) / tot
                gb = sum(b * n for b, n in zip(bs, ns)) / tot
            hist.append({"round": r + 1, "global_accuracy": _acc(X, y, gw, gb)})
        return hist, gw, gb

    hist_avg, gw_a, gb_a = run_federated(0.0)
    hist_prox, gw_p, gb_p = run_federated(args.mu)

    # client_drift on final FedAvg
    drifts = []
    for c in range(args.clients):
        mask = client_ids == c
        if np.any(mask):
            drifts.append(_acc(X[mask], y[mask], gw_a, gb_a))
    client_drift = float(np.std(drifts)) if drifts else 0.0

    methods = {
        "local_only": {"global_accuracy": acc_local},
        "centralized": {"global_accuracy": acc_central},
        "FedAvg": {
            "global_accuracy": hist_avg[-1]["global_accuracy"] if hist_avg else 0.0,
            "communication_rounds": args.rounds,
            "history": hist_avg,
        },
        "FedProx": {
            "global_accuracy": hist_prox[-1]["global_accuracy"] if hist_prox else 0.0,
            "communication_rounds": args.rounds,
            "mu": args.mu,
            "history": hist_prox,
        },
    }
    primary = methods["FedProx"]["global_accuracy"]
    metrics = {
        "primary_metric": primary,
        "global_accuracy": primary,
        "methods": methods,
        "partition_method": "dirichlet",
        "non_iid_type": "dirichlet",
        "non_iid_degree": float(1.0 / max(args.alpha, 1e-6)),
        "alpha": args.alpha,
        "num_clients": args.clients,
        "participation_rate": args.participation,
        "local_epochs": args.local_epochs,
        "communication_rounds": args.rounds,
        "client_drift": client_drift,
        "fedprox_mu": args.mu,
        "seed": args.seed,
        "baselines": ["local_only", "centralized", "FedAvg", "FedProx"],
        "note": "standard Non-IID baseline compare; local simulation only",
    }
    Path(args.out).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({k: metrics[k] for k in metrics if k != "methods"}))
    print(json.dumps({"methods_summary": {m: methods[m].get("global_accuracy") for m in methods}}))


if __name__ == "__main__":
    main()
'''

RUN_FEDAVG = r'''#!/usr/bin/env python3
"""Unified entry used by fl_pack_service.run_local_fedavg_pilot()."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    script = HERE / "hfl_fedavg_pilot.py"
    out = HERE / "_last_fedavg_metrics.json"
    proc = subprocess.run(
        [sys.executable, str(script), "--rounds", "5", "--clients", "5", "--out", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.is_file():
        print(out.read_text(encoding="utf-8"))
        return
    print(proc.stdout or proc.stderr or json.dumps({"error": "fedavg pilot failed", "code": proc.returncode}))


if __name__ == "__main__":
    main()
'''


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)

    index = []
    all_facts = []
    for p in PAPERS:
        pid = p["id"]
        paper_domain = p.get("domain") or "fl_core"
        body = {k: v for k, v in p.items()}
        body["domain"] = paper_domain
        w(f"papers/{pid}.facts.json", json.dumps(body, ensure_ascii=False, indent=2))
        index.append(
            {
                "id": pid,
                "title": p["title"],
                "year": p["year"],
                "setting": p["setting"],
                "domain": paper_domain,
                "external_id": p["external_id"],
                "file": f"papers/{pid}.facts.json",
            }
        )
        for f in p["facts"]:
            fact = dict(f)
            fact["paper_id"] = pid
            fact["title"] = p["title"]
            fact["year"] = p["year"]
            fact["external_id"] = p["external_id"]
            fact["domain"] = f.get("domain") or paper_domain
            all_facts.append(fact)

    w("papers/index.json", json.dumps({"papers": index, "fact_count": len(all_facts)}, ensure_ascii=False, indent=2))
    w("papers/seed_facts.json", json.dumps({"facts": all_facts}, ensure_ascii=False, indent=2))

    for name, text in DATASETS.items():
        w(f"datasets/{name}", text)

    w("scripts/README.md", SCRIPTS_README)
    w("scripts/hfl_fedavg_pilot.py", HFL_FEDAVG)
    w("scripts/hfl_non_iid_partition.py", HFL_NONIID)
    w("scripts/hfl_dirichlet_partition.py", HFL_DIRICHLET)
    w("scripts/hfl_baseline_compare_pilot.py", HFL_BASELINE_COMPARE)
    w("scripts/vfl_aligned_logistic_pilot.py", VFL_PILOT)
    w("scripts/run_fedavg_pilot.py", RUN_FEDAVG)

    # 实验范式资源（默认 standard_non_iid）
    w(
        "experiment_paradigms/profiles.json",
        json.dumps(
            {"default_profile": "standard_non_iid", "profiles": EXPERIMENT_PROFILES},
            ensure_ascii=False,
            indent=2,
        ),
    )
    w(
        "experiment_paradigms/partitions.json",
        json.dumps({"partitions": PARTITIONS_CATALOG}, ensure_ascii=False, indent=2),
    )
    w(
        "experiment_paradigms/baselines.json",
        json.dumps({"baselines": BASELINES_CATALOG}, ensure_ascii=False, indent=2),
    )
    w(
        "experiment_paradigms/metrics.json",
        json.dumps({"metrics": METRICS_CATALOG}, ensure_ascii=False, indent=2),
    )

    w(
        "checklists/hfl_metrics.md",
        """# HFL 指标与写作清单

- global_accuracy / local_accuracy
- communication_rounds / communication_cost_mb
- num_clients / participation_rate
- partition_method / non_iid_type / non_iid_degree / alpha（Dirichlet）
- client_drift
- 基线对比：Local Only、Centralized、FedAvg、FedProx（标准 Non-IID 档位必报）
- 报告须写明：划分方式、α、是否小样、是否单机模拟
""",
    )
    w(
        "checklists/vfl_metrics.md",
        """# VFL 指标与写作清单

- alignment_success_rate / aligned_sample_rate（建议阈值 ≥ 0.85）
- party 级 AUC / accuracy
- privacy_budget / communication_cost_mb
- alignment_key、feature_party、label_party
- 对齐失败应作为反例写入结果讨论，勿编造成功指标
""",
    )

    w(
        "failure_cases/alignment_mismatch.json",
        json.dumps(
            {
                "id": "alignment_mismatch",
                "setting": "vfl",
                "summary": "实体对齐键缺失或错配导致 alignment_success_rate 过低",
                "typical_symptoms": ["aligned_sample_rate < 0.85", "训练样本骤减"],
                "report_hint": "可作为「当前方法难以在未对齐数据上验证假设」的反例",
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    w(
        "failure_cases/non_iid_collapse.json",
        json.dumps(
            {
                "id": "non_iid_collapse",
                "setting": "hfl",
                "summary": "极端标签偏斜下 FedAvg 全局精度崩溃",
                "typical_symptoms": ["client_drift 升高", "global_accuracy 远低于集中训练"],
                "report_hint": "讨论 Non-IID 边界；建议 FedProx 或更频繁聚合",
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    w(
        "failure_cases/communication_blowup.json",
        json.dumps(
            {
                "id": "communication_blowup",
                "setting": "both",
                "summary": "为追精度无节制增加通信轮次导致成本不可接受",
                "typical_symptoms": ["communication_rounds 过大", "communication_cost_mb 失控"],
                "report_hint": "在局限中写清通信预算，避免只报精度",
            },
            ensure_ascii=False,
            indent=2,
        ),
    )

    manifest = {
        "version": "1.4.0",
        "name": "fl_starter_pack",
        "settings": ["hfl", "vfl", "both"],
        "default_experiment_profile": "standard_non_iid",
        "domains": [
            "fl_core",
            "finance_risk",
            "smart_care",
            "edge_mobile",
            "iot_industrial",
            "smart_transport",
            "privacy_crypto",
            "fl_cv",
            "fl_nlp",
            "fl_multilingual",
            "fl_blockchain",
            "fl_rl",
            "fl_continual",
            "llm_ft",
            "fl_lora_hetero",
        ],
        "description": "FL starter pack v1.4: experiment paradigms (default standard Non-IID Dirichlet+FedProx)",
        "runtime": "local_simulation_only",
        "papers": [p["file"] for p in index],
        "seed_facts_file": "papers/seed_facts.json",
        "datasets": [f"datasets/{k}" for k in DATASETS],
        "experiment_paradigms": {
            "profiles": "experiment_paradigms/profiles.json",
            "partitions": "experiment_paradigms/partitions.json",
            "baselines": "experiment_paradigms/baselines.json",
            "metrics": "experiment_paradigms/metrics.json",
        },
        "scripts": [
            {
                "path": "scripts/hfl_fedavg_pilot.py",
                "setting": "hfl",
                "recommended_when": "HFL + FedAvg pilot",
            },
            {
                "path": "scripts/hfl_non_iid_partition.py",
                "setting": "hfl",
                "recommended_when": "HFL + label-skew Non-IID partition",
            },
            {
                "path": "scripts/hfl_dirichlet_partition.py",
                "setting": "hfl",
                "recommended_when": "标准 Non-IID：Dirichlet/pathological 划分",
                "profile": "standard_non_iid",
            },
            {
                "path": "scripts/hfl_baseline_compare_pilot.py",
                "setting": "hfl",
                "recommended_when": "标准 Non-IID：Local/Centralized/FedAvg/FedProx 对比",
                "profile": "standard_non_iid",
            },
            {
                "path": "scripts/vfl_aligned_logistic_pilot.py",
                "setting": "vfl",
                "recommended_when": "VFL + alignment logistic",
            },
            {
                "path": "scripts/run_fedavg_pilot.py",
                "setting": "hfl",
                "recommended_when": "service entry for local FedAvg",
            },
        ],
        "checklists": ["checklists/hfl_metrics.md", "checklists/vfl_metrics.md"],
        "failure_cases": [
            "failure_cases/alignment_mismatch.json",
            "failure_cases/non_iid_collapse.json",
            "failure_cases/communication_blowup.json",
        ],
        "schema": {
            "paper_facts": [
                "fact_id",
                "claim",
                "method",
                "setting",
                "domain",
                "metrics",
                "dataset",
                "limitations",
                "source",
                "quote",
                "relevance",
            ],
            "dataset_yaml": [
                "id",
                "name",
                "setting",
                "domain",
                "download_url",
                "partition",
                "schema",
                "pilot_subset",
                "upload_requirement",
            ],
            "experiment_profile": [
                "id",
                "partition",
                "baselines",
                "metrics",
                "report_must_include",
            ],
        },
    }
    w("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    w(
        "SCHEMA.md",
        """# FL Pack Schema

- `papers/*.facts.json`: paper metadata + `facts[]` aligned to literature_facts fields
- `papers/seed_facts.json`: flattened facts for project seeding
- `datasets/*.yaml`: dataset metadata (not full LEAF dumps)
- `scripts/*.py`: local pilots writing `metrics.json`
- `failure_cases/*.json`: negative examples for report discussion
""",
    )
    print(f"Wrote FL pack to {ROOT}")


if __name__ == "__main__":
    main()
