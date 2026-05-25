import { Card } from '@/components/Card';
import { CheckCircle, Clock, Target } from 'lucide-react';
import type { ExperimentDesign } from '@/types';

interface ExperimentDesignTableProps {
  experiments: ExperimentDesign[];
}

export const ExperimentDesignTable = ({ 
  experiments 
}: ExperimentDesignTableProps) => {
  return (
    <Card>
      <h3 className="text-lg font-semibold text-white mb-4">
        实验设计
      </h3>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                步骤
              </th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                实验名称
              </th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                描述
              </th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                预期结果
              </th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                成功标准
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {experiments.map((exp) => (
              <tr 
                key={exp.id}
                className="hover:bg-gray-800/50 transition-colors"
              >
                <td className="py-4 px-4">
                  <div className="flex items-center gap-2">
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-500/20 text-blue-400 font-bold text-sm">
                      {exp.step}
                    </div>
                  </div>
                </td>
                <td className="py-4 px-4">
                  <div className="flex items-center gap-2">
                    <Target className="w-4 h-4 text-green-400" />
                    <span className="font-medium text-white">{exp.name}</span>
                  </div>
                </td>
                <td className="py-4 px-4">
                  <p className="text-sm text-gray-300 max-w-xs">{exp.description}</p>
                </td>
                <td className="py-4 px-4">
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-yellow-400" />
                    <p className="text-sm text-gray-300 max-w-xs">{exp.expected_result}</p>
                  </div>
                </td>
                <td className="py-4 px-4">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-400" />
                    <p className="text-sm text-gray-300 max-w-xs">{exp.success_criteria}</p>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};
