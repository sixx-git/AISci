import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Loader2, MessageSquare, Sparkles, Bot, User } from 'lucide-react';
import { Button } from '@/components/Button';
import datasetService, { type ModelingResult } from '@/services/datasetService';
import { cn } from '@/lib/utils';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  action?: string;
}

interface DatasetModelingChatPanelProps {
  datasetId: string;
  datasetName: string;
  onModelingResult?: (result: ModelingResult | null) => void;
}

const QUICK_PROMPTS = [
  '运行自动建模，分析数据并给出基线模型',
  '做质量分析，检查缺失与异常',
  '预处理数据',
  '简要介绍这个数据集适合做什么研究',
];

export function DatasetModelingChatPanel({
  datasetId,
  datasetName,
  onModelingResult,
}: DatasetModelingChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages([]);
    onModelingResult?.(null);
  }, [datasetId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, busy]);

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || !datasetId || busy) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: trimmed,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setBusy(true);

    try {
      const history = [...messages, userMsg].map((m) => ({
        role: m.role,
        content: m.content,
      }));
      const res = await datasetService.assistantChat(datasetId, {
        message: trimmed,
        history: history.slice(0, -1),
      });

      if (res.code === 200 && res.data) {
        const data = res.data;
        setMessages((prev) => [
          ...prev,
          {
            id: `a-${Date.now()}`,
            role: 'assistant',
            content: data.reply,
            action: data.action,
          },
        ]);
        if (data.modeling_result?.success) {
          onModelingResult?.(data.modeling_result);
        }
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: `a-${Date.now()}`,
            role: 'assistant',
            content: res.message || '处理失败，请重试',
          },
        ]);
      }
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: 'assistant',
          content: e instanceof Error ? e.message : '请求失败',
        },
      ]);
    } finally {
      setBusy(false);
    }
  }, [datasetId, busy, messages, onModelingResult]);

  return (
    <div className="space-y-3">
      <p className="text-xs text-bp-muted">
        已选数据集：<span className="text-bp-text font-medium">{datasetName}</span>
        。用自然语言描述你想做的处理，例如建模、质量分析或预处理。
      </p>

      <div
        ref={scrollRef}
        className="min-h-[200px] max-h-[320px] overflow-y-auto rounded-bp border border-bp-border bg-bp-base/50 p-3 space-y-3 scrollbar-thin scrollbar-thumb-bp-muted"
      >
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8 text-center text-bp-muted">
            <MessageSquare className="w-8 h-8 mb-2 opacity-40" />
            <p className="text-xs">发送消息开始对话，或点击下方快捷指令</p>
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              'flex gap-2 text-xs',
              msg.role === 'user' ? 'justify-end' : 'justify-start',
            )}
          >
            {msg.role === 'assistant' && (
              <div className="w-6 h-6 rounded-full bg-bp-cyan-tint border border-bp-cyan/20 flex items-center justify-center shrink-0">
                <Bot className="w-3.5 h-3.5 text-bp-cyan" />
              </div>
            )}
            <div
              className={cn(
                'max-w-[85%] rounded-bp px-3 py-2 leading-relaxed',
                msg.role === 'user'
                  ? 'bg-bp-cyan-tint border border-bp-cyan/20 text-bp-text'
                  : 'bg-bp-panel border border-bp-border text-bp-text',
              )}
            >
              {msg.content}
              {msg.action && msg.action !== 'answer_only' && (
                <span className="block mt-1 text-xs text-bp-muted">
                  操作：{msg.action}
                </span>
              )}
            </div>
            {msg.role === 'user' && (
              <div className="w-6 h-6 rounded-full bg-bp-panel border border-bp-border flex items-center justify-center shrink-0">
                <User className="w-3.5 h-3.5 text-bp-muted" />
              </div>
            )}
          </div>
        ))}
        {busy && (
          <div className="flex items-center gap-2 text-xs text-bp-muted">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-bp-cyan" />
            正在处理…
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {QUICK_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => sendMessage(prompt)}
            disabled={busy}
            className="text-xs px-2 py-1 rounded-full border border-bp-border text-bp-muted hover:text-bp-cyan hover:border-bp-cyan/30 transition-colors disabled:opacity-50"
          >
            <Sparkles className="w-2.5 h-2.5 inline mr-0.5 -mt-px" />
            {prompt.length > 18 ? `${prompt.slice(0, 18)}…` : prompt}
          </button>
        ))}
      </div>

      <div className="flex gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              sendMessage(input);
            }
          }}
          placeholder="例如：用 model_type 做分类预测 / 检查缺失值并预处理"
          rows={2}
          disabled={busy}
          className="input-field flex-1 py-2 text-sm resize-none min-h-[44px]"
        />
        <Button
          variant="primary"
          size="sm"
          icon={busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          onClick={() => sendMessage(input)}
          disabled={busy || !input.trim()}
          className="self-end"
        >
          发送
        </Button>
      </div>
    </div>
  );
}
