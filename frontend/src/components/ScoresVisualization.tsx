import { useState } from 'react';
import { Card } from '@/components/Card';
import { 
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend
} from 'recharts';
import { BarChart3, Radar as RadarIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Hypothesis } from '@/types';

interface ScoresVisualizationProps {
  hypotheses: Hypothesis[];
  selectedHypothesisId?: string;
}

const SCORE_LABELS = {
  novelty: '新颖性',
  feasibility: '可行性',
  scientific_value: '科学价值',
  clarity: '清晰度',
  testability: '可验证性'
};

const COLORS = [
  '#3b82f6', // blue
  '#8b5cf6', // purple
  '#ec4899', // pink
  '#f59e0b', // amber
  '#10b981'  // green
];

export const ScoresVisualization = ({ 
  hypotheses, 
  selectedHypothesisId 
}: ScoresVisualizationProps) => {
  const [chartType, setChartType] = useState<'radar' | 'bar'>('radar');

  // 转换数据用于图表
  const radarData = Object.entries(SCORE_LABELS).map(([key, label]) => {
    const item: any = { subject: label };
    hypotheses.forEach((hyp) => {
      item[`hyp_${hyp.id}`] = hyp.scores[key as keyof typeof hyp.scores];
    });
    return item;
  });

  const barData = hypotheses.map((hyp) => ({
    name: hyp.title,
    新颖性: hyp.scores.novelty,
    可行性: hyp.scores.feasibility,
    科学价值: hyp.scores.scientific_value,
    清晰度: hyp.scores.clarity,
    可验证性: hyp.scores.testability,
    总分: hyp.score
  }));

  return (
    <Card>
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-white">评分可视化</h3>
        <div className="flex items-center gap-2 bg-gray-800 rounded-lg p-1">
          <button
            onClick={() => setChartType('radar')}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
              chartType === 'radar' 
                ? 'bg-blue-600 text-white' 
                : 'text-gray-400 hover:text-white'
            )}
          >
            <RadarIcon className="w-4 h-4" />
            雷达图
          </button>
          <button
            onClick={() => setChartType('bar')}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
              chartType === 'bar' 
                ? 'bg-blue-600 text-white' 
                : 'text-gray-400 hover:text-white'
            )}
          >
            <BarChart3 className="w-4 h-4" />
            条形图
          </button>
        </div>
      </div>

      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          {chartType === 'radar' ? (
            <RadarChart data={radarData}>
              <PolarGrid stroke="#374151" />
              <PolarAngleAxis 
                dataKey="subject" 
                tick={{ fill: '#9ca3af', fontSize: 12 }} 
              />
              <PolarRadiusAxis 
                angle={90} 
                domain={[0, 100]} 
                tick={{ fill: '#6b7280' }} 
              />
              {hypotheses.map((hyp, idx) => (
                <Radar
                  key={hyp.id}
                  name={hyp.title}
                  dataKey={`hyp_${hyp.id}`}
                  stroke={COLORS[idx % COLORS.length]}
                  fill={COLORS[idx % COLORS.length]}
                  fillOpacity={selectedHypothesisId ? 
                    (selectedHypothesisId === hyp.id ? 0.5 : 0.1) : 0.3}
                  strokeWidth={selectedHypothesisId ?
                    (selectedHypothesisId === hyp.id ? 3 : 1) : 2}
                />
              ))}
              <Legend 
                wrapperStyle={{ paddingTop: '20px' }}
                formatter={(value: string) => hypotheses.find(h => `hyp_${h.id}` === value)?.title}
              />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#1f2937', 
                  border: '1px solid #374151',
                  borderRadius: '8px'
                }}
                labelStyle={{ color: '#9ca3af' }}
              />
            </RadarChart>
          ) : (
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis 
                dataKey="name" 
                tick={{ fill: '#9ca3af', fontSize: 11 }} 
                angle={-15}
                textAnchor="end"
                height={80}
              />
              <YAxis 
                domain={[0, 100]} 
                tick={{ fill: '#6b7280' }} 
              />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#1f2937', 
                  border: '1px solid #374151',
                  borderRadius: '8px'
                }}
              />
              <Legend wrapperStyle={{ paddingTop: '10px' }} />
              <Bar dataKey="新颖性" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="可行性" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="科学价值" fill="#f59e0b" radius={[4, 4, 0, 0]} />
              <Bar dataKey="可验证性" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </Card>
  );
};
