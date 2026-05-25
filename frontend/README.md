# AI Scientist Frontend

使用 React + TypeScript + Vite + TailwindCSS 构建的智能科研助手前端。

## 技术栈

- React 18
- TypeScript
- Vite
- TailwindCSS
- React Router 6
- Axios
- Lucide Icons
- React Markdown

## 快速开始

### 安装依赖

```bash
cd frontend
npm install
```

### 开发模式

```bash
npm run dev
```

访问 http://localhost:3000

### 构建生产版本

```bash
npm run build
```

## 功能页面

| 页面 | 路径 | 功能 |
|------|------|------|
| 首页 | `/` | 项目列表展示 |
| 创建项目 | `/projects/new` | 新建科研项目 |
| 项目工作台 | `/projects/:id` | 项目主页面，包含 PDF 上传、研究问题输入、Pipeline 运行和结果展示 |
| 文档管理 | `/documents` | 文档管理页面 |
| 设置 | `/settings` | 设置页面 |

## 项目结构

```
frontend/
├── src/
│   ├── components/       # UI 组件
│   │   ├── Navbar.tsx
│   │   ├── Button.tsx
│   │   ├── Card.tsx
│   │   └── StatusBadge.tsx
│   ├── pages/           # 页面组件
│   │   ├── Home.tsx
│   │   ├── CreateProject.tsx
│   │   ├── ProjectWorkspace.tsx
│   │   ├── Documents.tsx
│   │   └── Settings.tsx
│   ├── lib/             # 工具函数和 API
│   │   ├── api.ts
│   │   └── utils.ts
│   ├── types/           # TypeScript 类型定义
│   │   └── index.ts
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
└── README.md
```
