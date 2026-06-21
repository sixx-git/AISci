"""
Prompt 加载器
从 backend/prompts 目录加载 Prompt 模板并支持变量替换
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional


logger = logging.getLogger(__name__)


class PromptLoader:
    """
    Prompt 加载器类
    负责从文件系统加载 Prompt 模板并处理变量替换
    """

    def __init__(self, prompts_dir: Optional[str] = None):
        """
        初始化 Prompt 加载器

        Args:
            prompts_dir: Prompt 模板目录路径，如果为 None 则使用默认路径
        """
        if prompts_dir is None:
            # 获取默认的 prompts 目录路径
            current_dir = Path(__file__).parent
            backend_dir = current_dir.parent.parent
            self.prompts_dir = backend_dir / "prompts"
        else:
            self.prompts_dir = Path(prompts_dir)

        logger.info(f"Prompt 模板目录: {self.prompts_dir}")

        # 检查目录是否存在
        if not self.prompts_dir.exists():
            raise FileNotFoundError(f"Prompt 目录不存在: {self.prompts_dir}")

        # 缓存已加载的模板
        self._cached_templates: Dict[str, str] = {}

    def load_template(self, template_name: str) -> str:
        """
        加载 Prompt 模板

        Args:
            template_name: 模板名称（可以带或不带 .md 扩展名）

        Returns:
            Prompt 模板内容字符串

        Raises:
            FileNotFoundError: 如果模板文件不存在
        """
        # 确保文件名以 .md 结尾
        if not template_name.endswith('.md'):
            template_name = f"{template_name}.md"

        # 检查缓存
        if template_name in self._cached_templates:
            logger.debug(f"从缓存加载模板: {template_name}")
            return self._cached_templates[template_name]

        # 查找模板文件
        template_path = self.prompts_dir / template_name

        if not template_path.exists():
            raise FileNotFoundError(f"Prompt 模板文件不存在: {template_path}")

        # 读取模板文件
        logger.info(f"加载 Prompt 模板: {template_path}")
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()

        # 缓存模板
        self._cached_templates[template_name] = template_content

        return template_content

    def render_template(
        self,
        template_name: str,
        variables: Dict[str, Any]
    ) -> str:
        """
        渲染 Prompt 模板，替换变量

        Args:
            template_name: 模板名称
            variables: 变量字典，键为变量名，值为变量值

        Returns:
            渲染后的 Prompt 字符串

        Raises:
            FileNotFoundError: 如果模板文件不存在
            KeyError: 如果模板中的变量在变量字典中找不到
        """
        # 加载模板
        template_content = self._resolve_template_content(template_name, variables)

        # 渲染模板 - 使用双花括号格式 {{variable}}
        rendered_content = template_content

        # 替换每个变量
        for var_name, var_value in variables.items():
            placeholder = f"{{{{{var_name}}}}}"
            # 确保变量值是字符串
            value_str = str(var_value) if var_value is not None else ""
            rendered_content = rendered_content.replace(placeholder, value_str)

        # 检查是否还有未替换的变量
        import re
        unprocessed_vars = re.findall(r'{{(\w+)}}', rendered_content)
        if unprocessed_vars:
            logger.warning(f"模板中仍有未替换的变量: {unprocessed_vars}")

        return rendered_content

    def _resolve_template_content(self, template_name: str, variables: Dict[str, Any]) -> str:
        """优先使用项目级 override，否则加载默认模板。"""
        try:
            from app.services.prompt_context import get_project_id
            project_id = get_project_id()
            if project_id:
                from app.core.database import SessionLocal
                from app.services.prompt_override_service import get_prompt_override_service
                db = SessionLocal()
                try:
                    svc = get_prompt_override_service(db)
                    return svc.get_effective_template(project_id, template_name.replace(".md", ""))
                finally:
                    db.close()
        except Exception as exc:
            logger.debug(f"Prompt override 解析失败，使用默认模板: {exc}")
        return self.load_template(template_name)

    def clear_cache(self) -> None:
        """
        清空模板缓存
        """
        self._cached_templates.clear()
        logger.debug("Prompt 模板缓存已清空")

    def list_templates(self) -> list:
        """
        列出所有可用的 Prompt 模板

        Returns:
            模板名称列表（不带 .md 扩展名）
        """
        templates = []
        for file_path in self.prompts_dir.glob('*.md'):
            template_name = file_path.stem
            templates.append(template_name)
        return sorted(templates)


# 全局单例
_prompt_loader: Optional[PromptLoader] = None


def get_prompt_loader() -> PromptLoader:
    """
    获取 PromptLoader 单例

    Returns:
        PromptLoader 实例
    """
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader()
    return _prompt_loader
