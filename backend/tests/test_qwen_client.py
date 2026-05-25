"""
Qwen Client 单元测试
"""
import json
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 尝试导入，可能失败
try:
    from app.services.qwen_client import (
        QwenClient,
        QwenError,
        QwenAPIError,
        QwenTimeoutError,
        get_qwen_client
    )
    HAS_QWEN = True
except ImportError as e:
    HAS_QWEN = False
    print(f"Warning: Qwen imports failed: {e}")


class TestQwenClient(TestCase):
    """QwenClient 单元测试"""
    
    def setUp(self):
        """设置测试环境"""
        if not HAS_QWEN:
            self.skipTest("Qwen imports not available")
        
        self.mock_api_key = "test-api-key"
    
    @patch('app.services.qwen_client.openai.OpenAI')
    def test_client_initialization(self, mock_openai):
        """测试客户端初始化"""
        client = QwenClient(
            api_key="test-key",
            base_url="https://test.url",
            model="qwen-max"
        )
        
        mock_openai.assert_called_once()
        self.assertEqual(client.api_key, "test-key")
        self.assertEqual(client.base_url, "https://test.url")
        self.assertEqual(client.model, "qwen-max")
    
    @patch('app.services.qwen_client.openai.OpenAI')
    def test_chat_success(self, mock_openai_class):
        """测试 chat 方法成功调用"""
        # Mock OpenAI client
        mock_client_instance = MagicMock()
        mock_openai_class.return_value = mock_client_instance
        
        # Mock response
        mock_choice = MagicMock()
        mock_choice.message.content = "这是测试回复"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client_instance.chat.completions.create.return_value = mock_response
        
        client = QwenClient(
            api_key=self.mock_api_key,
            base_url="https://test.base.url",
            model="qwen-test"
        )
        
        # 调用方法
        result = client.chat("你好", system_prompt="你是一个测试助手", temperature=0.5)
        
        # 验证
        self.assertEqual(result, "这是测试回复")
        mock_client_instance.chat.completions.create.assert_called_once()
    
    @patch('app.services.qwen_client.openai.OpenAI')
    def test_structured_chat_success(self, mock_openai_class):
        """测试 structured_chat 方法成功调用"""
        # Mock OpenAI client
        mock_client_instance = MagicMock()
        mock_openai_class.return_value = mock_client_instance
        
        # Mock response
        mock_choice = MagicMock()
        mock_choice.message.content = '{"answer": "这是结构化回复", "confidence": 0.95}'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client_instance.chat.completions.create.return_value = mock_response
        
        client = QwenClient(
            api_key=self.mock_api_key,
            base_url="https://test.base.url",
            model="qwen-test"
        )
        
        # 调用方法
        schema_example = {"answer": "", "confidence": 0.0}
        result = client.structured_chat(
            "这是一个测试问题",
            schema_example=schema_example,
            system_prompt="你是一个测试助手"
        )
        
        # 验证
        self.assertIsInstance(result, dict)
        self.assertEqual(result["answer"], "这是结构化回复")
        self.assertEqual(result["confidence"], 0.95)
    
    @patch('app.services.qwen_client.openai.OpenAI')
    def test_structured_chat_with_markdown(self, mock_openai_class):
        """测试 structured_chat 处理 markdown 格式的响应"""
        # Mock OpenAI client
        mock_client_instance = MagicMock()
        mock_openai_class.return_value = mock_client_instance
        
        # Mock response with markdown
        mock_choice = MagicMock()
        mock_choice.message.content = '''```json
{"answer": "这是 markdown 包裹的回复", "confidence": 0.9}
```'''
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client_instance.chat.completions.create.return_value = mock_response
        
        client = QwenClient(
            api_key=self.mock_api_key,
            base_url="https://test.base.url",
            model="qwen-test"
        )
        
        # 调用方法
        result = client.structured_chat("测试问题")
        
        # 验证
        self.assertIsInstance(result, dict)
        self.assertEqual(result["answer"], "这是 markdown 包裹的回复")
    
    @patch('app.services.qwen_client.openai.OpenAI')
    def test_structured_chat_invalid_json(self, mock_openai_class):
        """测试 structured_chat 处理无效 JSON"""
        # Mock OpenAI client
        mock_client_instance = MagicMock()
        mock_openai_class.return_value = mock_client_instance
        
        # Mock response with invalid JSON
        mock_choice = MagicMock()
        mock_choice.message.content = "这不是有效的 JSON"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client_instance.chat.completions.create.return_value = mock_response
        
        client = QwenClient(
            api_key=self.mock_api_key,
            base_url="https://test.base.url",
            model="qwen-test"
        )
        
        # 调用方法
        result = client.structured_chat("测试问题")
        
        # 验证应该返回包含原始内容的字典
        self.assertIsInstance(result, dict)
        self.assertIn("raw_response", result)
        self.assertIn("error", result)
    
    @patch('app.services.qwen_client.openai.OpenAI')
    def test_chat_with_messages(self, mock_openai_class):
        """测试 chat_with_messages 方法"""
        # Mock OpenAI client
        mock_client_instance = MagicMock()
        mock_openai_class.return_value = mock_client_instance
        
        # Mock response
        mock_choice = MagicMock()
        mock_choice.message.content = "这是多轮对话回复"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client_instance.chat.completions.create.return_value = mock_response
        
        client = QwenClient(
            api_key=self.mock_api_key,
            base_url="https://test.base.url",
            model="qwen-test"
        )
        
        # 调用方法
        messages = [
            {"role": "system", "content": "你是测试助手"},
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！有什么我可以帮助的？"},
            {"role": "user", "content": "测试问题"}
        ]
        result = client.chat_with_messages(messages)
        
        # 验证
        self.assertEqual(result, "这是多轮对话回复")
    
    def test_no_api_key_error(self):
        """测试未设置 API Key 时的错误"""
        client = QwenClient(api_key="")
        with self.assertRaises(QwenError):
            client.chat("测试问题")
    
    @patch('app.services.qwen_client.openai.OpenAI')
    def test_convenience_functions(self, mock_openai_class):
        """测试便捷函数"""
        # Mock
        mock_client_instance = MagicMock()
        mock_openai_class.return_value = mock_client_instance
        
        mock_choice = MagicMock()
        mock_choice.message.content = '{"result": "ok"}'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client_instance.chat.completions.create.return_value = mock_response
        
        # 测试便捷函数
        from app.services.qwen_client import _qwen_client
        _qwen_client = None  # 重置单例
        
        # 测试 get_qwen_client
        client = get_qwen_client()
        self.assertIsInstance(client, QwenClient)
        client2 = get_qwen_client()
        self.assertIs(client, client2)  # 应该是同一个实例


if __name__ == '__main__':
    import unittest
    unittest.main()
