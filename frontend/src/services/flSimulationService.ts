/**
 * 联邦仿真 API（仅 federated_learning 项目）
 */
import api from '@/lib/api';
import type {
  ApiResponse,
  FlSimBackend,
  FlSimulationCapabilities,
  FlSimulationConfig,
  FlSimulationRunResult,
  FlSimulationSpec,
} from '@/types';

function unwrap<T>(res: ApiResponse<T>, fallbackMsg = '请求失败'): T {
  if (res.code !== 200 || res.data === undefined || res.data === null) {
    throw new Error(res.message || fallbackMsg);
  }
  return res.data;
}

export type FlSimRunPayload = FlSimulationSpec & { backend?: FlSimBackend };

export const flSimulationService = {
  async getCapabilities(projectId: string): Promise<FlSimulationCapabilities> {
    const res = await api.get<ApiResponse<FlSimulationCapabilities>>(
      `/projects/${projectId}/fl-simulation/capabilities`,
    );
    return unwrap(res.data, '获取仿真能力失败');
  },

  async getConfig(projectId: string): Promise<FlSimulationConfig> {
    const res = await api.get<ApiResponse<FlSimulationConfig>>(
      `/projects/${projectId}/fl-simulation/config`,
    );
    return unwrap(res.data, '获取仿真配置失败');
  },

  async patchConfig(
    projectId: string,
    patch: FlSimRunPayload,
  ): Promise<FlSimulationConfig> {
    const res = await api.patch<ApiResponse<FlSimulationConfig>>(
      `/projects/${projectId}/fl-simulation/config`,
      patch,
    );
    return unwrap(res.data, '更新仿真配置失败');
  },

  async run(
    projectId: string,
    experimentId: string,
    payload: FlSimRunPayload = {},
  ): Promise<{ result: FlSimulationRunResult; experiment?: Record<string, unknown> }> {
    const res = await api.post<
      ApiResponse<{ result: FlSimulationRunResult; experiment?: Record<string, unknown> }>
    >(
      `/projects/${projectId}/experiments/${experimentId}/fl-simulation/run`,
      payload,
      { timeout: 180_000 },
    );
    return unwrap(res.data, '运行仿真失败');
  },

  async getLatest(
    projectId: string,
    experimentId: string,
  ): Promise<{ result: FlSimulationRunResult | null; history_count: number }> {
    const res = await api.get<
      ApiResponse<{ result: FlSimulationRunResult | null; history_count: number }>
    >(`/projects/${projectId}/experiments/${experimentId}/fl-simulation/latest`);
    return unwrap(res.data, '获取仿真结果失败');
  },
};

export default flSimulationService;
