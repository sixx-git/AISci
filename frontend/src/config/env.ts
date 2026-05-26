/**
 * 统一环境变量读取入口
 * 所有环境变量必须以 VITE_ 开头
 */

export const env = {
  /** 是否使用 Mock 数据模式 */
  USE_MOCK: import.meta.env.VITE_USE_MOCK === 'true',

  /** 后端 API 基础地址。空字符串表示使用 Vite proxy（开发模式） */
  API_BASE_URL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
} as const;

// 类型安全断言
type Env = typeof env;
type EnvKeys = keyof Env;

// 验证必要变量
const requiredVars: EnvKeys[] = ['USE_MOCK', 'API_BASE_URL'];
for (const key of requiredVars) {
  if (env[key] === undefined) {
    console.warn(`[Env] 缺少环境变量: ${key}`);
  }
}

export default env;