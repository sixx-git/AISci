import React, { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft,
  Upload,
  Play,
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
  History,
} from 'lucide-react';
import { projectApi, documentApi, pipelineApi } from '@/lib/api';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { StatusBadge } from '@/components/StatusBadge';
import { PipelineVisualization, PipelineStage as VisualPipelineStage } from '@/components/PipelineVisualization';
import { ResearchResults } from '@/components/ResearchResults';
import { PipelineHistory } from '@/components/PipelineHistory';
import type { Project, Document, PipelineRunDetail } from '@/types';

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
  const [uploading, setUploading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [selectedRun, setSelectedRun] = useState<PipelineRunDetail | null>(null);

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
    setPipelineCompleted(false);
    setSelectedRun(null);

    // 重置所有阶段为 pending 状态
    setPipelineStages(VISUAL_PIPELINE_STAGES.map(stage => ({
      ...stage,
      status: 'pending',
      output: undefined
    })));

    try {
      // 调用真实的 API
      const response = await pipelineApi.run(projectId, researchQuestion);
      if (response.code === 200) {
        setPipelineCompleted(true);
        
        // 更新所有阶段状态为成功
        setPipelineStages(VISUAL_PIPELINE_STAGES.map((stage) => ({
          ...stage,
          status: 'success' as const,
          duration: '0s',
        })));
        
        // 刷新历史记录
        if (showHistory) {
          await new Promise(resolve => setTimeout(resolve, 1000));
          // 历史记录会通过 PipelineHistory 组件自动刷新
        }
      }
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
      alert('Pipeline 运行失败，请重试');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
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
        <Button
          onClick={() => setShowHistory(!showHistory)}
          variant="secondary"
          icon={<History className="w-4 h-4" />}
        >
          {showHistory ? '隐藏历史' : '查看历史'}
        </Button>
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
              icon={<Play className="w-4 h-4" />}
              className="w-full"
            >
              {isRunning ? '研究中...' : '运行研究 Pipeline'}
            </Button>
          </Card>
          
          {/* History Panel - Conditional */}
          {showHistory && projectId && (
            <PipelineHistory 
              projectId={projectId} 
              onSelectRun={setSelectedRun}
            />
          )}
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
          {selectedRun ? (
            <Card title={`历史运行结果 - ${selectedRun.research_question.substring(0, 30)}...`} subtitle="历史记录查看">
              <div className="p-4 bg-gray-900/50 rounded-lg">
                <p className="text-white">运行时间: {new Date(selectedRun.created_at).toLocaleString('zh-CN')}</p>
                <p className="text-gray-400 mt-2">状态: {selectedRun.status}</p>
                <div className="mt-4">
                  <p className="text-sm text-gray-400 mb-2">阶段详情:</p>
                  <div className="space-y-2">
                    {selectedRun.stages.map((stage) => (
                      <div key={stage.id} className="flex justify-between items-center p-2 bg-gray-800/50 rounded">
                        <span className="text-sm text-white">{stage.stage}</span>
                        <StatusBadge status={stage.status as any} />
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </Card>
          ) : pipelineCompleted ? (
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
