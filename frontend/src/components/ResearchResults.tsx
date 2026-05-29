import { useState } from 'react';
import { Card } from '@/components/Card';
import { ScoresVisualization } from '@/components/ScoresVisualization';
import { LiteratureEvidenceComponent } from '@/components/LiteratureEvidence';
import { ExperimentDesignTable } from '@/components/ExperimentDesignTable';
import { Button } from '@/components/Button';
import { Sparkles, FileText, Download, Award, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ResearchResult, Hypothesis } from '@/types';

interface ResearchResultsProps {
  results?: ResearchResult;
}

export const ResearchResults = ({ 
  results = {} as ResearchResult
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
            <CompactHypothesisCard
              key={hyp.id}
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

function getScoreColor(score: number) {
  if (score >= 85) return 'text-green-400';
  if (score >= 70) return 'text-yellow-400';
  return 'text-orange-400';
}

function getScoreBg(score: number) {
  if (score >= 85) return 'bg-green-500/20';
  if (score >= 70) return 'bg-yellow-500/20';
  return 'bg-orange-500/20';
}

function CompactHypothesisCard({ hypothesis, isSelected, onSelect, index }: {
  hypothesis: Hypothesis;
  isSelected: boolean;
  onSelect: () => void;
  index: number;
}) {
  return (
    <Card
      className={cn(
        'cursor-pointer transition-all duration-200 hover:border-blue-500/50',
        isSelected && 'border-blue-500 bg-blue-500/5',
      )}
      onClick={onSelect}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500">
            <span className="text-white font-bold text-sm">{index + 1}</span>
          </div>
          <div>
            <div className="flex items-center gap-1">
              <Sparkles className="w-4 h-4 text-yellow-400" />
              <h4 className="font-semibold text-white">{hypothesis.title}</h4>
            </div>
          </div>
        </div>
        <div className={cn(
          'px-3 py-1 rounded-full text-sm font-bold',
          getScoreBg(hypothesis.score),
          getScoreColor(hypothesis.score),
        )}>
          {hypothesis.score}/100
        </div>
      </div>
      <p className="text-gray-300 text-sm mb-4 line-clamp-3">{hypothesis.description}</p>
      <div className="grid grid-cols-2 gap-2">
        {([
          ['新颖性', hypothesis.scores.novelty, CheckCircle2, 'text-blue-400'],
          ['可行性', hypothesis.scores.feasibility, CheckCircle2, 'text-green-400'],
          ['科学价值', hypothesis.scores.scientific_value, Award, 'text-yellow-400'],
          ['可验证性', hypothesis.scores.testability, CheckCircle2, 'text-purple-400'],
        ] as const).map(([label, score, Icon, iconColor]) => (
          <div key={label} className="flex items-center gap-2">
            <Icon className={cn('w-4 h-4', iconColor)} />
            <div className="flex-1">
              <div className="flex justify-between text-xs mb-1">
                <span className="text-gray-400">{label}</span>
                <span className={getScoreColor(score)}>{score}</span>
              </div>
              <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
                <div className={cn('h-full rounded-full transition-all duration-500', getScoreBg(score))}
                  style={{ width: `${score}%` }} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
