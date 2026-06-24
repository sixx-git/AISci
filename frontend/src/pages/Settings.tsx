import { KeyRound, Terminal, Info } from 'lucide-react';
import { PageHeader } from '@/components/PageHeader';
import { Card } from '@/components/Card';
import { LlmConfigForm } from '@/components/settings/LlmConfigForm';

const ENV_HINTS = [
  { key: 'QWEN_API_KEY', desc: 'DashScope API 密钥，供 Pipeline 与智能体调用' },
  { key: 'QWEN_MODEL', desc: '默认模型 ID（可被页面配置覆盖）' },
  { key: 'USE_MOCK_LLM', desc: '设为 true 时使用模拟 LLM，无需真实 Key 即可跑通流程' },
  { key: 'QWEN_BASE_URL', desc: '可选，自定义 OpenAI 兼容端点' },
] as const;

export function Settings() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <PageHeader
        title="设置"
        subtitle="配置 LLM API、模型与系统选项"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        <div className="lg:col-span-2 space-y-6">
          <Card
            title="LLM API 配置"
            subtitle="Qwen 全模态 · 文本与视觉共用"
          >
            <LlmConfigForm idPrefix="settings-llm" />
          </Card>
        </div>

        <div className="space-y-6">
          <Card
            title="环境变量说明"
            subtitle="backend/.env"
          >
            <div className="space-y-3">
              {ENV_HINTS.map((item) => (
                <div
                  key={item.key}
                  className="p-3 rounded-bp border border-bp-border bg-bp-panel/30"
                >
                  <code className="text-xs font-mono text-bp-cyan">{item.key}</code>
                  <p className="text-[11px] text-bp-muted mt-1 leading-relaxed">{item.desc}</p>
                </div>
              ))}
            </div>
          </Card>

          <Card title="快速指引">
            <ul className="space-y-3 text-xs text-bp-muted">
              <li className="flex gap-2">
                <KeyRound className="w-4 h-4 text-bp-cyan shrink-0 mt-0.5" />
                <span>
                  顶栏 <strong className="text-bp-text font-normal">API 管理</strong> 下拉与本文配置同步，保存后立即生效。
                </span>
              </li>
              <li className="flex gap-2">
                <Terminal className="w-4 h-4 text-bp-green shrink-0 mt-0.5" />
                <span>
                  开发调试可设置 <code className="text-bp-cyan">USE_MOCK_LLM=true</code>，无需外网 Key。
                </span>
              </li>
              <li className="flex gap-2">
                <Info className="w-4 h-4 text-bp-yellow shrink-0 mt-0.5" />
                <span>
                  自定义密钥仅存于后端会话，不会写入前端本地存储。
                </span>
              </li>
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
