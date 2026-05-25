import { Card } from '@/components/Card';
import { BookOpen, Quote, Lightbulb } from 'lucide-react';
import type { LiteratureEvidence } from '@/types';

interface LiteratureEvidenceProps {
  evidence: LiteratureEvidence[];
}

const TYPE_ICONS = {
  citation: BookOpen,
  quote: Quote,
  concept: Lightbulb
};

const TYPE_LABELS = {
  citation: '引用',
  quote: '引述',
  concept: '概念'
};

const TYPE_COLORS = {
  citation: 'text-blue-400 bg-blue-500/20',
  quote: 'text-green-400 bg-green-500/20',
  concept: 'text-purple-400 bg-purple-500/20'
};

export const LiteratureEvidenceComponent = ({ 
  evidence 
}: LiteratureEvidenceProps) => {
  return (
    <Card>
      <h3 className="text-lg font-semibold text-white mb-4">
        文献证据来源
      </h3>

      <div className="space-y-4">
        {evidence.map((item, idx) => {
          const Icon = TYPE_ICONS[item.source_type];
          
          return (
            <div
              key={item.id}
              className="p-4 rounded-lg border border-gray-700 bg-gray-800/50 hover:border-gray-600 transition-colors"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className={cn(
                    'p-2 rounded-lg',
                    TYPE_COLORS[item.source_type]
                  )}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="font-medium text-white">{item.title}</h4>
                      <span className={cn(
                        'px-2 py-0.5 rounded text-xs font-medium',
                        TYPE_COLORS[item.source_type]
                      )}>
                        {TYPE_LABELS[item.source_type]}
                      </span>
                    </div>
                    <p className="text-sm text-gray-400">
                      {item.author} ({item.year})
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium text-green-400">
                    {item.relevance}% 相关
                  </div>
                </div>
              </div>

              <blockquote className="text-gray-300 text-sm border-l-2 border-gray-600 pl-4 py-1 italic">
                "{item.content}"
              </blockquote>
            </div>
          );
        })}
      </div>
    </Card>
  );
};

// 添加缺失的 cn 导入
import { cn } from '@/lib/utils';
