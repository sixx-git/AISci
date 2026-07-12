import type { LucideIcon } from 'lucide-react';
import {
  LayoutDashboard, HelpCircle, BookOpen, Database,
  GitBranch, Lightbulb, FlaskConical, FileText, ScrollText, SlidersHorizontal,
} from 'lucide-react';

export interface ProjectTabItem {
  id: string;
  label: string;
  icon: LucideIcon;
}

/** 一级 Tab：科研主链（8 个，含概览） */
export const PRIMARY_PROJECT_TABS: ProjectTabItem[] = [
  { id: 'overview', label: '项目概览', icon: LayoutDashboard },
  { id: 'questions', label: '研究问题', icon: HelpCircle },
  { id: 'literature', label: '文献库', icon: BookOpen },
  { id: 'datasets', label: '数据集', icon: Database },
  { id: 'workflow', label: '智能体工作流', icon: GitBranch },
  { id: 'hypotheses', label: '候选假设', icon: Lightbulb },
  { id: 'experiments', label: '实验设计', icon: FlaskConical },
  { id: 'reports', label: '研究报告', icon: FileText },
];

/** 高级 Tab：不显示在顶栏，保留 URL 深链 */
export const ADVANCED_PROJECT_TABS: ProjectTabItem[] = [
  { id: 'prompts', label: 'Prompt 管理', icon: SlidersHorizontal },
  { id: 'logs', label: '运行日志', icon: ScrollText },
];

export const ADVANCED_PROJECT_TAB_IDS = new Set(ADVANCED_PROJECT_TABS.map((t) => t.id));

/** 全部 Tab（含高级），用于路由与类型 */
export const PROJECT_TABS: ProjectTabItem[] = [
  ...PRIMARY_PROJECT_TABS,
  ...ADVANCED_PROJECT_TABS,
];

export const VALID_PROJECT_TAB_IDS = new Set(PROJECT_TABS.map((t) => t.id));

export type ProjectTabId = (typeof PROJECT_TABS)[number]['id'];
