> **已废弃**：小样验证不再调用 LLM 生成元数据，改由 `SmallValidationAgent` 确定性构建结果并执行沙箱。保留本文件仅供历史参考。

> **Pipeline 阶段**: `small_validation`  
> **调用方**: ~~SmallValidationAgent~~（已停用）  
> **输出**: JSON 元数据 + 系统单独生成 `analysis_script`；沙箱产出 `artifacts` / `sandbox_execution`
