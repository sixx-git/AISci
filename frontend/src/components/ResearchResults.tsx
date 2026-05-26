import { useState } from 'react';
import { HypothesisCard } from '@/components/HypothesisCard';
import { ScoresVisualization } from '@/components/ScoresVisualization';
import { LiteratureEvidenceComponent } from '@/components/LiteratureEvidence';
import { ExperimentDesignTable } from '@/components/ExperimentDesignTable';
import { Button } from '@/components/Button';
import { Sparkles, FileText, Download } from 'lucide-react';
import type { ResearchResult } from '@/types';
import { MOCK_RESEARCH_RESULTS } from '@/data/mockData';

interface ResearchResultsProps {
  results?: ResearchResult;
}

export const ResearchResults = ({ 
  results = MOCK_RESEARCH_RESULTS 
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
