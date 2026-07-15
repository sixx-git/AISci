PRESET_SCENARIOS = {
    "drug_dosage": {
        "name": "药物剂量优化",
        "research_goal": "找到最优的药物剂量和给药频率组合，使疗效评分最大化，同时将副作用控制在可接受范围内（< 0.3）",
        "constraints": [
            "剂量范围: 10mg ~ 100mg",
            "给药频率: 1次/天 ~ 4次/天",
            "副作用评分不得超过 0.3",
        ],
        "executor_type": "simulation",
        "max_iterations": 10,
    },
    "material_formula": {
        "name": "材料配方优化",
        "research_goal": "优化合金材料的成分配比（碳、锰、硅含量），使抗拉强度最大化同时保持韧性不低于阈值",
        "constraints": [
            "碳含量: 0.1% ~ 0.5%",
            "锰含量: 0.5% ~ 2.0%",
            "硅含量: 0.2% ~ 1.0%",
            "韧性指标不低于 40J",
        ],
        "executor_type": "simulation",
        "max_iterations": 12,
    },
}
