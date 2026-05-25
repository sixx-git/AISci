import React, { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft,
  Upload,
  FileText,
  Play,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  Download,
  Sparkles,
  BookOpen,
  Brain,
  Layout,
  FlaskConical,
  BarChart,
  File,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { projectApi, documentApi, researchApi } from '../lib/api';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { StatusBadge } from '../components/StatusBadge';
import type { Project, Document, PipelineStage } from '../types';

const PIPELINE_STAGES = [
  { id: 'problem', name: '问题理解', icon: Brain },
  { id: 'literature', name: '文献挖掘', icon: BookOpen },
  { id: 'gaps', name: '知识缺口分析', icon: Layout },
  { id: 'hypothesis', name: '假设生成', icon: Sparkles },
  { id: 'experiment', name: '实验设计', icon: FlaskConical },
  { id: 'validation', name: '小样验证', icon: BarChart },
  { id: 'report', name: '报告生成', icon: FileText },
];

export function ProjectWorkspace() {
  const { projectId } = useParams<{ projectId: string }>();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [project, setProject] = useState<Project | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [researchQuestion, setResearchQuestion] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [pipelineStages, setPipelineStages] = useState<PipelineStage[]>([]);
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

    // 初始化 Pipeline 阶段
    const initialStages: PipelineStage[] = PIPELINE_STAGES.map((stage) => ({
      name: stage.name,
      status: 'pending',
    }));
    setPipelineStages(initialStages);

    try {
      let currentStage = 0;

      // 模拟 Pipeline 逐步运行
      for (let i = 0; i < PIPELINE_STAGES.length; i++) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        currentStage = i;

        setPipelineStages((prev) => {
          const newStages = [...prev];
          newStages[i] = { ...newStages[i], status: 'running' };
          if (i > 0) {
            newStages[i - 1] = { ...newStages[i - 1], status: 'completed' };
          }
          return newStages;
        });
      }

      // 标记最后一个阶段为完成
      setPipelineStages((prev) => {
        const newStages = [...prev];
        newStages[newStages.length - 1] = {
          ...newStages[newStages.length - 1],
          status: 'completed',
        };
        return newStages;
      });

      // 生成模拟结果
      const mockResults = {
        problem_understanding: {
          analysis: '已分析研究问题，确定了核心研究方向和边界条件。',
        },
        literature_facts: [
          { content: '已有研究表明深度学习在该领域具有显著优势', source: 'Paper 1' },
          { content: '当前方法在特定场景下仍存在局限性', source: 'Paper 2' },
        ],
        knowledge_gaps: {
          gaps: ['混合模型研究不足', '新数据集缺乏验证'],
        },
        hypothesis: {
          hypothesis: '我们提出的混合模型在本研究任务上能够显著提升性能',
          rationale: '基于文献分析和方法创新',
        },
        experiment_design: {
          methods: '对比实验设计，使用标准数据集和评估指标',
        },
      };

      setResults(mockResults);
      setReportUrl('http://localhost:3000/api/v1/reports/download/mock-report/pdf');
    } catch (error) {
      console.error('Pipeline 运行失败:', error);
      setPipelineStages((prev) => {
        const newStages = [...prev];
        const lastRunning = newStages.findIndex((s) => s.status === 'running');
        if (lastRunning !== -1) {
          newStages[lastRunning] = { ...newStages[lastRunning], status: 'error' };
        }
        return newStages;
      });
    } finally {
      setIsRunning(false);
    }
  };

  const getStageIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="w-5 h-5 text-gray-500" />;
      case 'running':
        return <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />;
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-green-400" />;
      case 'error':
        return <XCircle className="w-5 h-5 text-red-400" />;
      default:
        return <Clock className="w-5 h-5 text-gray-500" />;
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
              className="border-2 border-dashed border-dark-600 rounded-lg p-8 text-center cursor-pointer hover:border-primary-600 transition-all"
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
                    className="flex items-center gap-3 p-3 bg-dark-900/50 rounded-lg"
                  >
                    <File className="w-4 h-4 text-primary-400" />
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
              className="input-field resize-none mb-4"
              disabled={isRunning}
            />

            <Button
              onClick={runPipeline}
              isLoading={isRunning}
              disabled={!researchQuestion.trim()}
              icon={<Play className="w-4 h-4" />}
              className="w-full"
            >
              {isRunning ? '研究中...' : '运行研究 Pipeline'}
            </Button>
          </Card>
        </div>

        {/* Right Column - Pipeline & Results */}
        <div className="lg:col-span-2 space-y-6">
          {/* Pipeline Stages */}
          <Card title="研究 Pipeline" subtitle="AI 研究流程跟踪">
            <div className="space-y-3">
              {PIPELINE_STAGES.map((stage, index) => {
                const Icon = stage.icon;
                const stageStatus = pipelineStages[index]?.status || 'pending';

                return (
                  <div
                    key={stage.id}
                    className="flex items-center gap-4 p-3 rounded-lg bg-dark-900/50"
                  >
                    <div className="flex-shrink-0">
                      {getStageIcon(stageStatus)}
                    </div>
                    <div className="flex items-center gap-3 flex-1">
                      <Icon className="w-5 h-5 text-gray-400" />
                      <span className="text-sm text-gray-300">{stage.name}</span>
                    </div>
                    <StatusBadge status={stageStatus} />
                  </div>
                );
              })}
            </div>
          </Card>

          {/* Results Display */}
          <Card title="研究结果" subtitle="AI 生成的研究内容">
            {results ? (
              <div className="space-y-6">
                {/* Download Report */}
                {reportUrl && (
                  <div className="p-4 bg-primary-600/10 border border-primary-600/30 rounded-lg">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <FileText className="w-6 h-6 text-primary-400" />
                        <div>
                          <p className="text-white font-medium">研究报告已生成</p>
                          <p className="text-gray-400 text-sm">PDF 格式下载</p>
                        </div>
                      </div>
                      <a
                        href={reportUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <Button icon={<Download className="w-4 h-4" />}>
                          下载报告
                        </Button>
                      </a>
                    </div>
                  </div>
                )}

                {/* Results Content */}
                <div className="prose prose-invert prose-sm max-w-none">
                  <h3>问题理解</h3>
                  <p>{results.problem_understanding?.analysis}</p>

                  <h3>文献发现</h3>
                  <ul>
                    {results.literature_facts?.map((fact: any, i: number) => (
                      <li key={i}>
                        {fact.content} <span className="text-gray-500">— {fact.source}</span>
                      </li>
                    ))}
                  </ul>

                  <h3>知识缺口</h3>
                  <ul>
                    {results.knowledge_gaps?.gaps?.map((gap: string, i: number) => (
                      <li key={i}>{gap}</li>
                    ))}
                  </ul>

                  <h3>研究假设</h3>
                  <p>{results.hypothesis?.hypothesis}</p>
                  <p className="text-gray-400 text-sm">{results.hypothesis?.rationale}</p>
                </div>
              </div>
            ) : (
              <div className="text-center py-12">
                <Sparkles className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400">输入研究问题并运行 Pipeline 开始研究</p>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
