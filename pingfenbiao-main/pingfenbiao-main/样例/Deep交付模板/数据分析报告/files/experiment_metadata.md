# Experiment Metadata: FL-NonIID-Comparative-Study-2026

## 1. 实验核心目标

系统性对比FedAvg与FedProx两种聚合算法，在5种数据异构程度(α=0.1,0.5,1.0,5.0,10.0)下的：
- **收敛动态**: 达到稳态所需的通信轮数
- **最终性能**: 全局模型泛化准确率
- **漂移量化**: Client Drift的累积强度与影响

## 2. 算法配置详情

### 2.1 FedAvg (基准算法)
- **更新规则**: W_global = Σ(n_k/n) * W_local^k
- **特点**: 无显式异构处理机制，Non-IID下易受Client Drift影响

### 2.2 FedProx (对比算法)
- **更新规则**: W_global = Σ(n_k/n) * W_local^k，其中本地目标含近端项
- **本地优化**: min[ F_k(W) + (μ/2)‖W - W_global‖² ]
- **超参数**: μ = 0.01 (经验调优值)
- **理论优势**: 通过限制本地更新幅度，抑制Client Drift

## 3. 数据异构设置（关键实验变量）

| Alpha | 异构等级 | 典型客户端标签分布 | 预期挑战 |
|-------|----------|-------------------|----------|
| 0.1 | 极端 | 1-2个主导类别(>80%) | 严重Client Drift，收敛极慢 |
| 0.5 | 显著 | 2-3个主导类别(>60%) | 明显精度损失 |
| 1.0 | 中度 | 3-5个类别相对均衡 | 可接受的性能折中 |
| 5.0 | 轻度 | 多数类别均有代表 | 接近IID性能 |
| 10.0 | 近似IID | 均匀分布 | 理想基准 |

## 4. 模型与训练配置

| 配置项 | 设置值 | 说明 |
|--------|--------|------|
| 模型架构 | 5-Layer CNN | Conv(32)→Conv(64)→FC(512)→FC(10) |
| 激活函数 | ReLU | 含BatchNorm层 |
| 数据集 | CIFAR-10 | 50k训练/10k测试，10类平衡 |
| 本地Epochs | E=5 | 每轮本地训练遍历次数 |
| Batch Size | 32 | 本地训练批次 |
| 优化器 | SGD | 带动量(0.9) |
| 学习率 | 0.01 | 恒定，无衰减 |
| 客户端总数 | 100 | 每轮随机采样10个(C=0.1) |

## 5. 关键预期结论（基于已有研究）

### 5.1 收敛速度
- Alpha=10.0应在20-30轮内收敛
- Alpha=0.1可能需要80+轮或无法收敛

### 5.2 算法对比
- Alpha≥5.0: FedAvg与FedProx性能接近（差异<2%）
- Alpha≤1.0: FedProx应显著优于FedAvg（差距5-10%）

### 5.3 Client Drift量化
- Weight_Divergence稳态值与Alpha负相关
- FedProx的Weight_Divergence应低于FedAvg（同Alpha下）

## 6. 数据收集与处理

### 6.1 采集时间
- 2026年第一季度
- 实验环境: 模拟集群（非真实分布式，控制变量）

### 6.2 异常注入
- **网络延迟**: 5%概率客户端超时（Round≤5时记录为缺失值）
- **模拟目的**: 测试算法对掉线的鲁棒性（非本分析重点）

### 6.3 收敛判定实现
```python
# 伪代码说明
def check_convergence(acc_history, window=10, threshold=0.2):
    if len(acc_history) < window:
        return False
    recent = acc_history[-window:]
    return max(recent) - min(recent) < threshold
```

## 7. 分析时必须明确的边界条件

1. **固定变量**: 学习率、模型架构、客户端采样率均恒定，排除干扰
2. **单一变量原则**: 仅Alpha和Algorithm变化，确保因果推断有效
3. **统计显著性**: 每组条件单条曲线，关注趋势而非置信区间
4. **物理可实现性**: 所有指标必须在合理范围内（如Accuracy不可能>95%）
