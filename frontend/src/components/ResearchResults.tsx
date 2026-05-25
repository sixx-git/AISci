import { useState } from 'react';
import { HypothesisCard } from '@/components/HypothesisCard';
import { ScoresVisualization } from '@/components/ScoresVisualization';
import { LiteratureEvidenceComponent } from '@/components/LiteratureEvidence';
import { ExperimentDesignTable } from '@/components/ExperimentDesignTable';
import { Button } from '@/components/Button';
import { Download, FileText, Sparkles } from 'lucide-react';
import type { ResearchResult } from '@/types';

interface ResearchResultsProps {
  results?: ResearchResult;
}

// 模拟完整的研究结果
const MOCK_RESULTS: ResearchResult = {
  hypotheses: [
    {
      id: '1',
      title: '深度迁移学习优化方法',
      description: '本研究假设通过自适应特征选择和多层次知识迁移，可以显著提升深度学习模型在小数据集上的泛化能力，特别是在跨域任务中。',
      score: 92,
      scores: {
        novelty: 95,
        feasibility: 88,
        scientific_value: 94,
        clarity: 90,
        testability: 91
      }
    },
    {
      id: '2',
      title: '注意力机制的轻量化改进',
      description: '提出一种基于稀疏注意力的轻量化模型架构，可以在保持精度的同时，大幅减少计算资源消耗。',
      score: 86,
      scores: {
        novelty: 82,
        feasibility: 90,
        scientific_value: 85,
        clarity: 88,
        testability: 87
      }
    },
    {
      id: '3',
      title: '自监督预训练策略优化',
      description: '探索新型的对比学习损失函数，提高预训练阶段的特征表示质量。',
      score: 81,
      scores: {
        novelty: 80,
        feasibility: 85,
        scientific_value: 82,
        clarity: 78,
        testability: 81
      }
    }
  ],
  literature_evidence: [
    {
      id: '1',
      title: 'Deep Learning for Natural Language Processing',
      author: 'Zhang et al.',
      year: '2023',
      content: '迁移学习在小样本学习中取得了显著进展，但跨域泛化仍是重要挑战。',
      source_type: 'citation',
      relevance: 92
    },
    {
      id: '2',
      title: 'Attention Is All You Need',
      author: 'Vaswani et al.',
      year: '2017',
      content: '注意力机制彻底改变了序列建模，但计算复杂度较高。',
      source_type: 'quote',
      relevance: 88
    },
    {
      id: '3',
      title: 'Self-Supervised Learning Survey',
      author: 'Chen et al.',
      year: '2022',
      content: '对比学习是自监督学习中最有效的方法之一。',
      source_type: 'concept',
      relevance: 85
    }
  ],
  experiment_design: [
    {
      id: '1',
      step: 1,
      name: '基准模型训练',
      description: '使用标准预训练模型在目标数据集上训练，建立性能基准。',
      expected_result: '达到现有文献中的基准性能',
      success_criteria: '准确率在 ±5% 范围内'
    },
    {
      id: '2',
      step: 2,
      name: '特征空间分析',
      description: '分析不同层的特征表示，识别关键信息区域。',
      expected_result: '识别出任务相关的特征空间分布',
      success_criteria: '可视化结果支持假设'
    },
    {
      id: '3',
      step: 3,
      name: '改进方案实现',
      description: '实现提出的优化方法，进行对比实验。',
      expected_result: '性能显著优于基准方法',
      success_criteria: '准确率提升 ≥ 5%'
    },
    {
      id: '4',
      step: 4,
      name: '消融实验验证',
      description: '验证各个组件的有效性。',
      expected_result: '完整模型优于任一单独组件',
      success_criteria: '每一个组件贡献 ≥ 2% 性能提升'
    }
  ]
};

export const ResearchResults = ({ 
  results = MOCK_RESULTS 
}: ResearchResultsProps) => {
  const [selectedHypothesisId, setSelectedHypothesisId] = useState<string>(
    results.hypotheses[0]?.id
  );

  const handleDownload = (format: 'markdown' | 'pdf') => {
    const content = generateReportContent(results);
    
    if (format === 'markdown') {
      const blob = new Blob([content], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'research-report.md';
      a.click();
      URL.revokeObjectURL(url);
    } else {
      alert('PDF 下载功能需要后端支持');
    }
  };

  const generateReportContent = (data: ResearchResult) => {
    return `# AI Research Report

## 研究假设

${data.hypotheses.map((h, i) => `### ${i + 1}. ${h.title}
**评分:** ${h.score}/100

${h.description}

- 新颖性: ${h.scores.novelty}
- 可行性: ${h.scores.feasibility}
- 科学价值: ${h.scores.scientific_value}
- 清晰度: ${h.scores.clarity}
- 可验证性: ${h.scores.testability}`).join('\n\n')}

## 文献证据

${data.literature_evidence.map(e => `- ${e.title} (${e.author}, ${e.year}): "${e.content}"`).join('\n')}

## 实验设计

${data.experiment_design.map((exp) => `### 步骤 ${exp.step}: ${exp.name}
${exp.description}
- 预期: ${exp.expected_result}
- 标准: ${exp.success_criteria}`).join('\n\n')}

---
生成时间: ${new Date().toISOString()}
`;
  };

  return (
    <div className="space-y-6">
      {/* 标题和下载按钮 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Sparkles className="w-7 h-7 text-yellow-400" />
            研究结果
          </h2>
          <p className="text-gray-400 mt-1">
            查看详细的研究发现和实验设计
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            onClick={() => handleDownload('markdown')}
            icon={<FileText className="w-4 h-4" />}
          >
            下载 Markdown
          </Button>
          <Button
            variant="primary"
            onClick={() => handleDownload('pdf')}
            icon={<Download className="w-4 h-4" />}
          >
            下载 PDF
          </Button>
        </div>
      </div>

      {/* 候选假设卡片 */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">候选假设</h3>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {results.hypotheses.map((hyp, idx) => (
            <HypothesisCard
              key={hyp.id}
              variant="compact"
              hypothesis={hyp}
              index={idx}
              isSelected={selectedHypothesisId === hyp.id}
              onSelect={() => setSelectedHypothesisId(hyp.id)}
            />
          ))}
        </div>
      </div>

      {/* 评分可视化 */}
      <ScoresVisualization
        hypotheses={results.hypotheses}
        selectedHypothesisId={selectedHypothesisId}
      />

      {/* 两列布局 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <LiteratureEvidenceComponent evidence={results.literature_evidence} />
      </div>

      <ExperimentDesignTable experiments={results.experiment_design} />
    </div>
  );
};
