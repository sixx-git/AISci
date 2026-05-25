"""
后端简单测试脚本
"""
import sys
import os

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

print("=" * 60)
print("   AI Scientist Backend - 基础测试")
print("=" * 60)
print()

# 测试 1: 导入配置
print("[1/4] 测试配置导入...")
try:
    from app.core.config import get_settings
    settings = get_settings()
    print("   [OK] 配置导入成功")
    print(f"      - APP_NAME: {settings.APP_NAME}")
    print(f"      - VERSION: {settings.VERSION}")
    print(f"      - DATABASE_URL: {settings.DATABASE_URL}")
except Exception as e:
    print(f"   [FAIL] 配置导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# 测试 2: 导入数据库
print("[2/4] 测试数据库配置...")
try:
    from app.core.database import Base, engine
    print("   [OK] 数据库配置导入成功")
except Exception as e:
    print(f"   [FAIL] 数据库配置导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# 测试 3: 导入模型
print("[3/4] 测试模型导入...")
try:
    from app.models import project
    print("   [OK] 模型导入成功")
    print(f"      - Project 模型: {hasattr(project, 'Project')}")
    print(f"      - Document 模型: {hasattr(project, 'Document')}")
    print(f"      - ProjectStatus 枚举: {hasattr(project, 'ProjectStatus')}")
except Exception as e:
    print(f"   [FAIL] 模型导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# 测试 4: 导入 schemas
print("[4/4] 测试 schemas 导入...")
try:
    from app.schemas import common, project as project_schema
    print("   [OK] Schemas 导入成功")
    print(f"      - ResponseModel: {hasattr(common, 'ResponseModel')}")
    print(f"      - ProjectCreate: {hasattr(project_schema, 'ProjectCreate')}")
    print(f"      - UploadResponse: {hasattr(project_schema, 'UploadResponse')}")
except Exception as e:
    print(f"   [FAIL] Schemas 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 60)
print("   [OK] 所有基础测试通过！")
print("=" * 60)
print()
print("下一步操作:")
print("  1. 配置 .env 文件")
print("  2. 运行: python scripts/init_db.py")
print("  3. 启动后端: cd backend && uvicorn app.main:app --reload")
print("  4. 访问: http://localhost:8000/docs 查看 API 文档")
print()
