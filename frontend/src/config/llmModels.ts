/**
 * 百炼 DashScope 真实 Qwen 模型 ID（OpenAI 兼容模式）
 * @see https://help.aliyun.com/zh/model-studio/text-generation-model
 * @see https://bailian.console.aliyun.com/cn-beijing?tab=doc#/doc/?type=model&url=2840914
 */
export type QwenModelOption = {
  id: string;
  hint?: string;
};

export type QwenModelGroup = {
  label: string;
  models: QwenModelOption[];
};

/** 按代际分组的 Qwen 模型（不含第三方与历史快照） */
export const QWEN_MODEL_GROUPS: QwenModelGroup[] = [
  {
    label: 'Qwen3.7（最新推荐）',
    models: [
      { id: 'qwen3.7-max', hint: '最强推理，1M 上下文' },
      { id: 'qwen3.7-plus', hint: '能力与成本均衡，推荐首选' },
    ],
  },
  {
    label: 'Qwen3.6',
    models: [
      { id: 'qwen3.6-max-preview', hint: '旗舰预览' },
      { id: 'qwen3.6-plus', hint: '1M 上下文，工具调用' },
      { id: 'qwen3.6-flash', hint: '高性价比' },
    ],
  },
  {
    label: 'Qwen3.5',
    models: [
      { id: 'qwen3.5-plus', hint: '均衡型' },
      { id: 'qwen3.5-flash', hint: '轻量快速' },
      { id: 'qwen3.5-397b-a17b', hint: '开源规格' },
      { id: 'qwen3.5-122b-a10b', hint: '开源规格' },
      { id: 'qwen3.5-27b', hint: '开源规格' },
      { id: 'qwen3.5-35b-a3b', hint: '开源规格' },
    ],
  },
  {
    label: 'Qwen3',
    models: [
      { id: 'qwen3-max', hint: '上一代旗舰' },
      { id: 'qwen3-max-preview', hint: '预览版' },
    ],
  },
  {
    label: 'Qwen3-Coder（代码）',
    models: [
      { id: 'qwen3-coder-plus', hint: '代码生成 Plus' },
      { id: 'qwen3-coder-flash', hint: '代码生成 Flash' },
      { id: 'qwen3-coder-next', hint: '下一代代码模型' },
    ],
  },
  {
    label: '千问 Long / 经典',
    models: [
      { id: 'qwen-long', hint: '超长文档，10M 上下文' },
      { id: 'qwen-long-latest', hint: 'Long 最新版' },
      { id: 'qwen-plus', hint: '经典 Plus' },
      { id: 'qwen-max', hint: '经典 Max' },
      { id: 'qwen-flash', hint: '经典 Flash' },
      { id: 'qwen-turbo', hint: '经典 Turbo' },
    ],
  },
];

export const QWEN_MODEL_PRESETS = QWEN_MODEL_GROUPS.flatMap((g) =>
  g.models.map((m) => m.id),
) as readonly string[];

export const CUSTOM_MODEL_VALUE = '__custom__';

/** @deprecated 使用 QWEN_MODEL_PRESETS */
export const TEXT_MODEL_PRESETS = QWEN_MODEL_PRESETS;

export function formatModelOptionLabel(model: QwenModelOption): string {
  return model.hint ? `${model.id} — ${model.hint}` : model.id;
}
