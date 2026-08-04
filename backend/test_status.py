import sqlite3
conn = sqlite3.connect('d:/Workplace/AISci/backend/data/aiscientist.db')
cur = conn.cursor()

# 找出 IN_PROGRESS 状态的项目
cur.execute("""
    SELECT p.id, p.name, p.status,
           (SELECT COUNT(*) FROM pipeline_runs r WHERE r.project_id=p.id) as run_count,
           (SELECT r.status FROM pipeline_runs r WHERE r.project_id=p.id ORDER BY r.created_at DESC LIMIT 1) as latest_run_status,
           (SELECT r.completed_at FROM pipeline_runs r WHERE r.project_id=p.id ORDER BY r.created_at DESC LIMIT 1) as latest_completed_at
    FROM projects p WHERE p.status='IN_PROGRESS'
""")
rows = cur.fetchall()
print(f'IN_PROGRESS projects: {len(rows)}')
for r in rows:
    pid, name, status, run_count, latest_status, latest_comp = r
    print(f'  {pid[:8]} - {name}')
    print(f'    status={status} runs={run_count} latest_run_status={latest_status} latest_completed={latest_comp}')

# 修复：将这两个项目状态改为 COMPLETED
print('\nFixing...')
cur.execute("UPDATE projects SET status='COMPLETED' WHERE status='IN_PROGRESS'")
fixed = cur.rowcount
print(f'Updated {fixed} projects to COMPLETED')
conn.commit()

# 验证
cur.execute("SELECT status, COUNT(*) FROM projects GROUP BY status")
print('\nUpdated project statuses:')
for r in cur.fetchall():
    print(f'  status={r[0]!r:20s} count={r[1]}')

conn.close()
