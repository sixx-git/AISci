"""
ExperimentDesignAgent 测试
"""
import unittest
from unittest import TestCase
from unittest.mock import MagicMock, patch

from app.agents.experiment_design_agent import (
    ExperimentDesignAgent,
    EXPERIMENT_DESIGN_PROMPT_TEMPLATE
)


class TestExperimentDesignAgent(TestCase):
    """ExperimentDesignAgent 测试"""
    
    def setUp(self):
        """设置测试"""
        self.agent = ExperimentDesignAgent()
    
    def test_prompt_template(self):
        """测试 Prompt 模板"""
        # 测试模板包含关键要求
        self.assertIn("methods", EXPERIMENT_DESIGN_PROMPT_TEMPLATE)
        self.assertIn("datasets", EXPERIMENT_DESIGN_PROMPT_TEMPLATE)
        self.assertIn("source_data", EXPERIMENT_DESIGN_PROMPT_TEMPLATE)
        self.assertIn("target_data", EXPERIMENT_DESIGN_PROMPT_TEMPLATE)
        self.assertIn("baselines", EXPERIMENT_DESIGN_PROMPT_TEMPLATE)
        self.assertIn("metrics", EXPERIMENT_DESIGN_PROMPT_TEMPLATE)
        self.assertIn("experimental_steps", EXPERIMENT_DESIGN_PROMPT_TEMPLATE)
        self.assertIn("expected_results", EXPERIMENT_DESIGN_PROMPT_TEMPLATE)
        self.assertIn("limitations", EXPERIMENT_DESIGN_PROMPT_TEMPLATE)
        self.assertIn("科学假设与研究计划", EXPERIMENT_DESIGN_PROMPT_TEMPLATE)
    
    def test_format_hypothesis_info(self):
        """测试格式化假设信息"""
        hypothesis = "混合 CNN-Transformer 模型在医学影像任务中优于单一模型"
        rationale = "CNN 提取空间特征，Transformer 处理长距离依赖"
        novelty = "首次系统对比三种模型架构"
        
        result = self.agent._format_hypothesis_info(
            hypothesis=hypothesis,
            rationale=rationale,
            novelty=novelty
        )
        
        # 验证包含关键信息
        self.assertIn(hypothesis, result)
        self.assertIn(rationale, result)
        self.assertIn(novelty, result)
    
    def test_validate_and_normalize_result(self):
        """测试验证和标准化结果"""
        # 模拟一个完整的结果
        complete_result = {
            "methods": "详细的研究方法...",
            "datasets": "详细的数据集...",
            "source_data": "详细的源数据...",
            "target_data": "详细的目标数据...",
            "baselines": "详细的基线方法...",
            "metrics": "详细的评估指标...",
            "experimental_steps": "详细的实验步骤...",
            "expected_results": "详细的预期结果...",
            "limitations": "详细的局限性..."
        }
        
        result = self.agent._validate_and_normalize_result(complete_result)
        
        # 验证所有字段都存在
        self.assertIn("methods", result)
        self.assertIn("datasets", result)
        self.assertIn("source_data", result)
        self.assertIn("target_data", result)
        self.assertIn("baselines", result)
        self.assertIn("metrics", result)
        self.assertIn("experimental_steps", result)
        self.assertIn("expected_results", result)
        self.assertIn("limitations", result)
        
        # 测试缺失字段的情况
        incomplete_result = {
            "methods": "只有方法...",
            "datasets": "只有数据集..."
        }
        
        result = self.agent._validate_and_normalize_result(incomplete_result)
        
        # 验证缺失字段被补全
        self.assertIn("source_data", result)
        self.assertIn("target_data", result)
        self.assertIn("baselines", result)
        self.assertIn("metrics", result)
        self.assertIn("experimental_steps", result)
        self.assertIn("expected_results", result)
        self.assertIn("limitations", result)
    
    @patch('app.agents.experiment_design_agent.qwen_structured_chat')
    def test_design_experiment_success(self, mock_qwen):
        """测试设计实验成功"""
        test_hypothesis = "混合 CNN-Transformer 模型在医学影像任务中优于单一模型"
        
        # 模拟 LLM 返回
        mock_qwen_result = {
            "methods": "本研究将实现三种模型架构进行对比：1) 纯 CNN 模型（如 ResNet），2) 纯 Transformer 模型（如 ViT），3) 混合 CNN-Transformer 模型。混合模型将采用 CNN 提取低层空间特征，然后通过 Transformer 编码器建模长距离依赖关系。所有模型将使用相同的训练策略和超参数设置。",
            "datasets": "使用公开的医学影像数据集：1) ChestX-ray14（胸部 X 光片，112,120 张图像），2) ChestX-ray8（胸部 X 光片，108,948 张图像），3) 自定义的医学影像数据集（如有合作数据）。所有数据集将按照 8:1:1 的比例划分为训练集、验证集和测试集。",
            "source_data": "源数据为 DICOM 或 JPEG 格式的医学影像，分辨率为 224x224 像素。预处理包括：1) 图像归一化，2) 数据增强（随机裁剪、旋转、翻转），3) 标签标准化。",
            "target_data": "目标数据为多标签分类结果，每个样本对应多种疾病的概率分布。输出格式为字典，键为疾病名称，值为预测概率。",
            "baselines": "基线方法包括：1) 纯 CNN 模型（ResNet-50），2) 纯 Transformer 模型（ViT-B/16），3) 经典的医学影像分类方法（如手工特征+SVM）。所有基线方法将在相同的数据集和评估设置下运行。",
            "metrics": "评估指标包括：1) 平均 AUC（Area Under Curve），2) 每个类别的 AUC，3) F1-score，4) 准确率，5) 召回率。主要比较平均 AUC 作为核心指标。",
            "experimental_steps": "实验步骤：1) 数据准备和预处理，2) 实现基线模型，3) 实现混合 CNN-Transformer 模型，4) 训练所有模型，5) 在测试集上评估，6) 对比分析结果，7) 消融实验验证各组件的作用。",
            "expected_results": "预期结果：1) 混合 CNN-Transformer 模型在平均 AUC 上显著优于纯 CNN 和纯 Transformer 模型，2) 混合模型在多种疾病分类任务上表现一致，3) 消融实验将验证 CNN 和 Transformer 组件的互补作用。",
            "limitations": "局限性：1) 实验仅在胸部 X 光片上验证，可能不适用于其他医学影像类型，2) 计算资源需求较高，训练时间较长，3) 数据集规模有限，可能存在过拟合风险，4) 未考虑领域自适应问题。"
        }
        
        mock_qwen.return_value = mock_qwen_result
        
        # 调用设计实验
        result = self.agent.design_experiment(
            hypothesis=test_hypothesis,
            rationale="CNN 提取空间特征，Transformer 处理长距离依赖",
            novelty="首次系统对比三种模型架构",
            testability="可以通过对比实验验证",
            required_data="公开医学影像数据集",
            possible_method="实现三个模型进行对比",
            risk="混合模型可能计算复杂度高"
        )
        
        # 验证
        self.assertIsNotNone(result)
        self.assertIn("methods", result)
        self.assertIn("datasets", result)
        self.assertIn("source_data", result)
        self.assertIn("target_data", result)
        self.assertIn("baselines", result)
        self.assertIn("metrics", result)
        self.assertIn("experimental_steps", result)
        self.assertIn("expected_results", result)
        self.assertIn("limitations", result)
        
        mock_qwen.assert_called_once()


if __name__ == '__main__':
    unittest.main()
