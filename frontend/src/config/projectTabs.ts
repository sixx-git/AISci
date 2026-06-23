import type { LucideIcon } from 'lucide-react';
import {
  LayoutDashboard, HelpCircle, BookOpen, Network, Database,
  GitBranch, Lightbulb, FlaskConical, FileText, ScrollText, Orbit, SlidersHorizontal,
} from 'lucide-react';

export interface ProjectTabItem {
  id: string;
  label: string;
  icon: LucideIcon;
}

export const PROJECT_TABS: ProjectTabItem[] = [
  { id: 'overview', label: '项目概览', icon: LayoutDashboard },
  { id: 'closed_loop', label: '科研闭环总览', icon: Orbit },
  { id: 'questions', label: '研究问题', icon: HelpCircle },
  { id: 'literature', label: '文献库', icon: BookOpen },
  { id: 'knowledge_graph', label: '知识图谱', icon: Network },
  { id: 'datasets', label: '数据集', icon: Database },
  { id: 'workflow', label: '智能体工作流', icon: GitBranch },
  { id: 'prompts', label: 'Prompt 管理', icon: SlidersHorizontal },
  { id: 'hypotheses', label: '候选假设', icon: Lightbulb },
  { id: 'experiments', label: '实验设计', icon: FlaskConical },
  { id: 'reports', label: '研究报告', icon: FileText },
  { id: 'logs', label: '运行日志', icon: ScrollText },
];

export const VALID_PROJECT_TAB_IDS = new Set(PROJECT_TABS.map((t) => t.id));

export type ProjectTabId = (typeof PROJECT_TABS)[number]['id'];
