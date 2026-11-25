"""6G 专业应用专题。模板是任务说明，不是文献 Fact，也不是设备实测。"""
from __future__ import annotations

from typing import Any, Dict, List

EMERGENCY_TOPIC = "emergency_comm"
COORDINATOR_ROLE = (
    "大家长只记录预检反馈、修订确认和版本状态，不自主作出容量、续航或方案是否可部署的专业决定。"
    "通过与否由确定性程序计算；没有检查工具的专题保持“待专业验证”。"
)

TOPICS: Dict[str, Dict[str, Any]] = {
    "emergency_comm": {
        "id": "emergency_comm",
        "label": "空天地融合应急通信",
        "domain": "6G融合通信 / 应急通信",
        "research_question": (
            "在空天地融合应急通信场景下，如何让候选通信保障方案满足基本资源约束，"
            "并能够根据确定性检查结果持续修订？"
        ),
        "research_goal": "形成可追溯的应急通信候选方案、资源约束预检和修订记录。",
        "research_background": (
            "虚拟近海岛屿在台风后部分地面通信失效。可用资源包括剩余地面网络、无人机中继和卫星回传。"
            "初始数字是模拟条件：30 台终端各 1 Mbps，卫星回传 20 Mbps，1 架无人机续航 60 分钟，任务 90 分钟。"
        ),
        "constraints": "不得把模拟参数写成文献事实或设备实测。预检通过不代表无线覆盖、时延或部署安全已验证。",
        "expected_output": "候选方案、程序预检结果、用户确认后的修订版本，以及可纳入报告的运行记录。",
        "keywords": "6G,应急通信,空天地融合,无人机中继,卫星回传",
        "tool": "emergency_constraints",
        "verification_status": "deterministic",
        "verification_note": "已实现回传容量、无人机续航、设备数量和参数完整性的程序检查。",
    },
    "edge_computing": {
        "id": "edge_computing",
        "label": "边缘智能与算网协同",
        "domain": "6G / 边缘智能 / 算网协同",
        "research_question": "在 6G 边缘智能场景中，计算任务分割与网络资源协同需要满足哪些可验证条件？",
        "research_goal": "利用文献、假设和评审整理算网协同的研究问题与证据缺口。",
        "research_background": "边缘节点、接入网和核心算力需要联合考虑时延、能耗和任务优先级。本专题当前没有专用仿真器。",
        "constraints": "没有算力、时延或能耗的确定性检查工具。相关结论标记为待专业验证，不能由大模型生成仿真结果。",
        "expected_output": "研究问题、文献事实、候选假设和明确标注待验证项的报告。",
        "keywords": "6G,边缘智能,算网协同,任务卸载",
        "tool": None,
        "verification_status": "待专业验证",
        "verification_note": "尚未接入算力、时延或能耗检查工具。完整科研分析可复用文献与假设流程。",
    },
    "isac": {
        "id": "isac",
        "label": "通感一体化研究",
        "domain": "6G / 通感一体化",
        "research_question": "通感一体化波形在通信质量与感知精度之间的折中，现有文献支持到什么程度？",
        "research_goal": "整理通感一体化的证据、知识缺口和可检验假设。",
        "research_background": "通信与感知共享频谱和硬件。本专题当前没有波形或感知精度的确定性检查器。",
        "constraints": "不得编造检测概率、距离分辨率或实测波形指标。缺少工具的判断保持待专业验证。",
        "expected_output": "带文献来源的研究分析，以及待专业验证事项清单。",
        "keywords": "6G,通感一体化,ISAC,波形",
        "tool": None,
        "verification_status": "待专业验证",
        "verification_note": "尚未接入通感指标检查工具。可以做文献与假设分析，不能输出虚假仿真。",
    },
    "custom": {
        "id": "custom",
        "label": "用户自定义6G任务",
        "domain": "6G",
        "research_question": "",
        "research_goal": "",
        "research_background": "",
        "constraints": "自定义问题中的数字在用户确认前只表示解析结果。大模型推测的参数不是真实设备参数。",
        "expected_output": "经用户核对的任务解析，以及按需进入的文献、假设和报告流程。",
        "keywords": "6G,自定义任务",
        "tool": None,
        "verification_status": "待专业验证",
        "verification_note": "自定义任务默认没有专用检查器。只有用户确认且专题本身带有工具时，才运行对应程序。",
    },
}


def list_topics() -> List[Dict[str, Any]]:
    return [public_topic(item) for item in TOPICS.values()]


def get_topic(topic_id: str | None) -> Dict[str, Any]:
    if topic_id in TOPICS:
        return TOPICS[topic_id]
    return TOPICS[EMERGENCY_TOPIC]


def public_topic(topic: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": topic["id"],
        "label": topic["label"],
        "domain": topic["domain"],
        "research_question": topic["research_question"],
        "research_goal": topic["research_goal"],
        "research_background": topic["research_background"],
        "constraints": topic["constraints"],
        "expected_output": topic["expected_output"],
        "keywords": topic["keywords"],
        "tool": topic["tool"],
        "verification_status": topic["verification_status"],
        "verification_note": topic["verification_note"],
        "coordinator_role": COORDINATOR_ROLE,
    }


def topic_id_from_config(config: Dict[str, Any] | None) -> str:
    app = (config or {}).get("sixg_app") or {}
    topic_id = app.get("topic_id")
    if topic_id in TOPICS:
        return topic_id
    return EMERGENCY_TOPIC
