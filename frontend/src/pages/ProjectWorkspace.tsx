import React, { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft,
  Upload,
  FileText,
  Play,
  Download,
  Sparkles,
  File,
  Brain,
  BookOpen,
  Layout,
  Sparkles as SparklesIcon,
  BarChart,
  FlaskConical,
  CheckCircle,
  FileText as FileTextIcon,
} from 'lucide-react';
import { projectApi, documentApi } from '@/lib/api';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import { PipelineVisualization, PipelineStage as VisualPipelineStage } from '@/components/PipelineVisualization';
import { ResearchResults } from '@/components/ResearchResults';
import type { Project, Document } from '@/types';

// 完整的 Pipeline 阶段定义（按用户要求的顺序）
const VISUAL_PIPELINE_STAGES: VisualPipelineStage[] = [
  { id: 'problem', name: '问题理解', icon: Brain, status: 'pending' },
  { id: 'literature', name: '文献挖掘', icon: BookOpen, status: 'pending' },
  { id: 'gaps', name: '知识缺口', icon: Layout, status: 'pending' },
  { id: 'hypothesis', name: '假设生成', icon: SparklesIcon, status: 'pending' },
  { id: 'evaluation', name: '假设评估', icon: BarChart, status: 'pending' },
  { id: 'experiment', name: '实验设计', icon: FlaskConical, status: 'pending' },
  { id: 'validation', name: '小样验证', icon: CheckCircle, status: 'pending' },
  { id: 'report', name: '报告生成', icon: FileTextIcon, status: 'pending' },
];

export function ProjectWorkspace() {
  const { projectId } = useParams<{ projectId: string }>();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [project, setProject] = useState<Project | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [researchQuestion, setResearchQuestion] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [pipelineStages, setPipelineStages] = useState<VisualPipelineStage[]>(VISUAL_PIPELINE_STAGES);
  const [pipelineCompleted, setPipelineCompleted] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [reportUrl, setReportUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (projectId) {
      loadProject();
      loadDocuments();
    }
  }, [projectId]);

  const loadProject = async () => {
    try {
      const response = await projectApi.get(projectId!);
      if (response.code === 200) {
        setProject(response.data);
      }
    } catch (error) {
      console.error('加载项目失败:', error);
    }
  };

  const loadDocuments = async () => {
    try {
      const response = await documentApi.list(projectId!);
      if (response.code === 200) {
        setDocuments(response.data || []);
      }
    } catch (error) {
      console.error('加载文档失败:', error);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !projectId) return;

    setUploading(true);
    try {
      const response = await documentApi.upload(projectId, file);
      if (response.code === 200) {
        await loadDocuments();
        alert('文档上传成功！');
      }
    } catch (error) {
      console.error('上传文档失败:', error);
      alert('上传失败，请重试');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const runPipeline = async () => {
    if (!researchQuestion.trim() || !projectId) return;

    setIsRunning(true);
    setResults(null);
    setReportUrl(null);
    setPipelineCompleted(false);

    // 重置所有阶段为 pending 状态
    setPipelineStages(VISUAL_PIPELINE_STAGES.map(stage => ({
      ...stage,
      status: 'pending',
      output: undefined
    })));

    try {
      // 逐个运行阶段
      for (let i = 0; i < VISUAL_PIPELINE_STAGES.length; i++) {
        const startTime = Date.now();
        
        // 设置当前阶段为 running
        setPipelineStages(prev => prev.map((stage, idx) => 
          idx === i ? { ...stage, status: 'running' as const } : stage
        ));

        // 模拟阶段执行
        await new Promise(resolve => setTimeout(resolve, 1200));

        const endTime = Date.now();
        const duration = ((endTime - startTime) / 1000).toFixed(1) + 's';

        // 模拟每个阶段的输出
        const stageOutputs = {
          problem: {
            analysis: '已深入理解研究问题的背景与重要性，明确了研究目标与边界条件。',
            keyInsights: [
              '问题具有重要的理论与实践价值',
              '现有研究存在明确缺口',
              '研究方案具有可行性'
            ]
          },
          literature: {
            papersAnalyzed: 23,
            keyFindings: [
              { id: 'f1', content: '深度学习在该领域应用广泛', source: 'Zhang et al., 2025' },
              { id: 'f2', content: 'Transformer架构展现出强大潜力', source: 'Wang et al., 2024' },
              { id: 'f3', content: '样本效率是核心挑战', source: 'Liu et al., 2025' }
            ],
            summary: '通过全面分析相关文献，确定了本领域的研究脉络与前沿动态。'
          },
          gaps: {
            identifiedGaps: [
              '混合模型在复杂场景中的探索不足',
              '跨域迁移学习的理论框架不完善',
              '小样本学习算法在该领域应用有限',
              '可解释性研究相对匮乏'
            ],
            priority: '高',
            impact: '解决这些缺口将推动领域显著进步'
          },
          hypothesis: {
            mainHypothesis: '结合注意力机制与图神经网络的混合模型将显著提升任务性能',
            subHypotheses: [
              '图神经网络能够有效建模结构化知识',
              '注意力机制增强了信息选择与组合能力',
              '迁移学习策略降低了数据依赖'
            ],
            rationale: '基于文献分析与方法论创新'
          },
          evaluation: {
            feasibility: 0.85,
            novelty: 0.78,
            impact: 0.92,
            riskAssessment: '低风险',
            recommendations: [
              '优先验证核心假设',
              '准备充足算力资源',
              '设计多组对比实验'
            ],
            overallScore: 8.2
          },
          experiment: {
            design: '严格的对照实验设计',
            datasets: ['Standard Benchmark A', 'Real-world Dataset B', 'Challenge Dataset C'],
            baselines: [
              '传统机器学习方法',
              '纯深度学习方法',
              '当前SOTA方法',
              '消融实验变体'
            ],
            metrics: ['准确率', '召回率', 'F1分数', '计算效率'],
            validationStrategy: '5折交叉验证'
          },
          validation: {
            experimentId: 'EXP-2025-001',
            results: {
              accuracy: '+12.5% 相对提升',
              f1: '+14.2% 相对提升',
              efficiency: '相当的推理速度'
            },
            statisticalSignificance: 'p < 0.01',
            conclusion: '初步验证表明假设成立'
          },
          report: {
            title: 'AI Research Report: A Hybrid Approach for Scientific Discovery',
            sections: [
              'Abstract',
              'Introduction',
              'Related Work',
              'Methodology',
              'Experiments',
              'Results',
              'Discussion',
              'Conclusion'
            ],
            recommendations: [
              '扩大实验规模',
              '探索更多应用场景',
              '优化计算效率',
              '撰写学术论文投稿'
            ],
            generatedAt: new Date().toISOString()
          }
        };

        const currentStageId = VISUAL_PIPELINE_STAGES[i].id as keyof typeof stageOutputs;
        
        // 更新阶段状态为 success 并保存输出
        setPipelineStages(prev => prev.map((stage, idx) => 
          idx === i ? { 
            ...stage, 
            status: 'success' as const, 
            output: stageOutputs[currentStageId],
            duration 
          } : stage
        ));
      }

      // 标记完成
      setPipelineCompleted(true);
      setReportUrl('http://localhost:3000/api/v1/reports/download/mock-report/pdf');
    } catch (error) {
      console.error('Pipeline 运行失败:', error);
      setPipelineStages(prev => {
        const newStages = [...prev];
        const lastRunning = newStages.findIndex((s) => s.status === 'running');
        if (lastRunning !== -1) {
          newStages[lastRunning] = { 
            ...newStages[lastRunning], 
            status: 'error' as const,
            output: { error: '执行失败，请重试', timestamp: new Date().toISOString() }
          };
        }
        return newStages;
      });
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <Link to="/" className="text-gray-400 hover:text-gray-200">
          <ArrowLeft className="w-6 h-6" />
        </Link>
        <div>
          <h1 className="text-3xl font-bold text-white mb-1">
            {project?.name || '项目工作台'}
          </h1>
          {project?.description && (
            <p className="text-gray-400">{project.description}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Inputs */}
        <div className="lg:col-span-1 space-y-6">
          {/* PDF Upload */}
          <Card title="文献上传" subtitle="上传相关文献 PDF">
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-gray-700 rounded-lg p-8 text-center cursor-pointer hover:border-blue-600 transition-all"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.txt,.docx"
                onChange={handleFileUpload}
                className="hidden"
              />
              <Upload className="w-10 h-10 text-gray-500 mx-auto mb-4" />
              <p className="text-gray-400 mb-2">
                {uploading ? '上传中...' : '点击或拖拽上传文件'}
              </p>
              <p className="text-gray-600 text-sm">支持 PDF, TXT, DOCX</p>
            </div>

            {/* Document List */}
            {documents.length > 0 && (
              <div className="mt-4 space-y-2">
                <h4 className="text-sm font-medium text-gray-400">已上传文档</h4>
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="flex items-center gap-3 p-3 bg-gray-900/50 rounded-lg"
                  >
                    <File className="w-4 h-4 text-blue-400" />
                    <span className="text-sm text-gray-300 flex-1 truncate">
                      {doc.filename}
                    </span>
                    <StatusBadge
                      status={(doc.status as any) || 'pending'}
                    />
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Research Question */}
          <Card title="研究问题" subtitle="输入您想研究的问题">
            <textarea
              value={researchQuestion}
              onChange={(e) => setResearchQuestion(e.target.value)}
              placeholder="例如：如何利用深度学习提升药物发现效率？"
              rows={6}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 resize-none mb-4"
              disabled={isRunning}
            />

            <Button
              onClick={runPipeline}
              isLoading={isRunning}
              disabled={!researchQuestion.trim()}
              leftIcon={<Play className="w-4 h-4" />}
              className="w-full"
            >
              {isRunning ? '研究中...' : '运行研究 Pipeline'}
            </Button>
          </Card>
        </div>

        {/* Right Column - Pipeline & Results */}
        <div className="lg:col-span-2 space-y-6">
          {/* Pipeline Visualization */}
          <Card title="研究 Pipeline" subtitle="AI 研究流程可视化">
            <PipelineVisualization 
              stages={pipelineStages}
            />
          </Card>

          {/* Results Display - 集成新的 ResearchResults 组件 */}
          {pipelineCompleted ? (
            <ResearchResults />
          ) : (
            <Card title="研究结果" subtitle="AI 生成的研究内容">
              <div className="text-center py-12">
                <Sparkles className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400">输入研究问题并运行 Pipeline 开始研究</p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
