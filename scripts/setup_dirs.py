"""
创建必要的目录
"""
import os

dirs = [
    'data',
    'storage',
    'storage/documents',
    'logs'
]

print("=" * 60)
print("   AI Scientist - 创建必要目录")
print("=" * 60)
print()

for dir_path in dirs:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        print(f"[OK] 已创建: {dir_path}")
    else:
        print(f"[OK] 已存在: {dir_path}")

print()
print("=" * 60)
print("[OK] 目录创建完成！")
print("=" * 60)
