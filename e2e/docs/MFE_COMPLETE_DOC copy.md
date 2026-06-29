# Superset 4.1 Module Federation (MFE) 完整实现文档

> 本文档系统记录了**从零实现** Superset 4.1 通过 Webpack Module Federation 暴露 Dashboard 给外部 Host 应用、定制化功能、解决各类 P0/P1 问题的完整流程，包括**架构图、关键代码、技术要点、问题根因分析**。

---

## 目录

- [1. 项目背景与目标](#1-项目背景与目标)
- [2. 整体架构](#2-整体架构)
- [3. 关键流程图](#3-关键流程图)
- [4. Host App 实现](#4-host-app-实现)
- [5. Superset Remote (MFE) 实现](#5-superset-remote-mfe-实现)
- [6. Webpack Module Federation 配置](#6-webpack-module-federation-配置)
- [7. 后端配置 (Superset)](#7-后端配置-superset)
- [8. 定制化功能](#8-定制化功能)
- [9. 关键技术问题与解决方案](#9-关键技术问题与解决方案)
- [10. 调试与回归测试清单](#10-调试与回归测试清单)
- [11. 启动流程](#11-启动流程)
- [12. 待办与未来工作](#12-待办与未来工作)

---

## 1. 项目背景与目标

### 1.1 原始需求

1. **MFE 暴露 Dashboard**：将 Superset Dashboard 作为 Module Federation Remote 暴露给任意 Host 应用。
2. **功能对齐 Embedded 模式**：选择了 Dashboard，应完整按照 Embedded 方式展示所有功能（与 iframe Embedded 体验一致，但使用原生 React 组件而非 iframe）。
3. **定制化功能**：
   - 砍掉 `view query` 等不需要的菜单项
   - 过滤器统一显示在顶部，可以折叠
   - 暗色模式支持（Superset 4.1 原生不提供）
4. **上下文共享**：Host 应用登录后，Superset Dashboard 自动使用同一份 Auth、Theme、Filters 上下文。

### 1.2 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Flask + Flask-AppBuilder 4.5.0 + PostgreSQL + Redis |
| 前端 | React 16.14.0 + Webpack 5 + Module Federation |
| 共享 UI 库 | antd, @emotion/react, react-router-dom |
| 国际化 | Jed (translator) + moment |
| 通信 | REST API + JWT Token + CSRF Token |

---

## 2. 整体架构

```
┌────────────────────────────────────────────────────────────────────────┐
│                            浏览器 (单页应用)                              │
│                                                                         │
│  ┌──────────────────────────┐    ┌────────────────────────────────────┐  │
│  │  Host App (port 3000)    │    │  Superset Dev Server (port 9000)   │  │
│  │  ────────────────────    │    │  ────────────────────────────      │  │
│  │  React 16.14.0           │    │  Webpack 5 + DevServer             │  │
│  │  ModuleFederationPlugin  │───>│  ModuleFederationPlugin            │  │
│  │  remotes:                │    │  name: 'superset'                  │  │
│  │   superset@9000/...      │    │  exposes:                          │  │
│  │                          │    │   ./Dashboard                      │  │
│  │  功能:                   │    │   ./MfeContext                     │  │
│  │  ✓ 登录 UI              │    │  shared (singleton):               │  │
│  │  ✓ Dark/Light 切换      │    │   react, react-dom, @emotion/react │  │
│  │  ✓ Dashboard ID 切换    │    │   react-router-dom                 │  │
│  │  ✓ 过滤器 UI            │    │  remoteEntry.js (≈700KB)           │  │
│  │                          │    │                                    │  │
│  │  <MfeContextProvider>   │    │  暴露的组件:                        │  │
│  │    └─ <SupersetDashboard>│   │   Dashboard.tsx (主入口)            │  │
│  │         (原生 React)     │    │   MfeContext.tsx (共享 Context)     │  │
│  │         非 iframe        │    │   mfePreamble.ts (前置初始化)       │  │
│  └──────────┬───────────────┘    └─────────────────┬──────────────────┘  │
│             │                                     │                     │
│             │ JWT (Authorization: Bearer ...)     │                     │
│             │ CSRF (X-CSRFToken / Cookie)         │                     │
│             ▼                                     ▼                     │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Superset Backend (Flask, port 8188)                                │ │
│  │  ──────────────────────────────────────                              │ │
│  │  REST API:                                                          │ │
│  │   POST /api/v1/security/login  → { access_token }                   │ │
│  │   GET  /api/v1/security/csrf_token/ → { result: "csrf-..." }       │ │
│  │   GET  /api/v1/me/  → 当前用户信息                                  │ │
│  │   GET  /api/v1/dashboard/{id}  → dashboard 元数据                  │ │
│  │   GET  /api/v1/dashboard/{id}/charts/  → chart 配置                │ │
│  │                                                                     │ │
│  │  FEATURE_FLAGS: { EMBEDDED_SUPERSET: true, ... }                   │ │
│  │  CORS: 启用 (ENABLE_CORS = True)                                    │ │
│  └──────────┬──────────────────────────────────┬──────────────────────┘ │
│             │                                  │                        │
│             ▼                                  ▼                        │
│  ┌────────────────────┐             ┌────────────────────┐              │
│  │  Docker PostgreSQL │             │  Docker Redis      │              │
│  │  (Superset 元数据)  │             │  (缓存/会话)        │              │
│  └────────────────────┘             └────────────────────┘              │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.1 端口规划

| 服务 | 端口 | 说明 |
|---|---|---|
| Superset 后端 (Flask) | 8188 | 提供 REST API |
| Superset 前端 DevServer | 9000 | MFE Remote，暴露 `superset/Dashboard` |
| MFE Host | 3000 | Host App，宿主应用 |
| PostgreSQL | 5432 | 数据库 (Docker) |
| Redis | 6379 | 缓存 (Docker) |

---

## 3. 关键流程图

### 3.1 MFE 启动与初始化时序图

```
 Host App (3000)            Network              Superset Dev (9000)         Superset BE (8188)
      │                       │                        │                          │
      │ 1. 加载 index.tsx     │                        │                          │
      │   (同步创建 #app      │                        │                          │
      │    元素并填充         │                        │                          │
      │    data-bootstrap)    │                        │                          │
      │                       │                        │                          │
      │ 2. import('./bootstrap')                        │                          │
      │   动态加载 host UI    │                        │                          │
      │                       │                        │                          │
      │ 3. 用户点击登录       │                        │                          │
      │   POST /api/v1/security/login                   │                          │
      │ ────────────────────────────────────────────────────────────────>         │
      │                       │                        │        4. 返回 access_token │
      │ <────────────────────────────────────────────────────────────────           │
      │                       │                        │                          │
      │ 5. GET /csrf_token/   │                        │                          │
      │   (Bearer JWT)        │                        │                          │
      │ ────────────────────────────────────────────────────────────────>         │
      │                       │                        │        6. 设置 csrf cookie │
      │ <────────────────────────────────────────────────────────────────           │
      │                       │                        │                          │
      │ 7. lazy import        │                        │                          │
      │   'superset/Dashboard'│                        │                          │
      │ ─────────────────────>│ 8. 加载 remoteEntry.js │                          │
      │                       │<───────────────────────│                          │
      │                       │ 9. 加载 shared chunks  │                          │
      │                       │<───────────────────────│                          │
      │                       │                        │                          │
      │                       │ 10. mfePreamble.ts     │                          │
      │                       │   - configure() 翻译器 │                          │
      │                       │   - initFeatureFlags() │                          │
      │                       │   - moment.locale()    │                          │
      │                       │   - window.__MFE_MODE__ = true                     │
      │                       │                        │                          │
      │                       │ 11. setupPlugins()     │                          │
      │                       │   - 注册所有 chart     │                          │
      │                       │                        │                          │
      │                       │ 12. RootContextProviders                         │
      │                       │   - preamble.ts        │                          │
      │                       │   - setupClient()      │                          │
      │                       │   - 触发 CSRF 请求     │                          │
      │                       │   ───────────────────────────────────────────────> │
      │                       │                        │        13. 200 OK         │
      │                       │   <────────────────────────────────────────────────│
      │                       │                        │                          │
      │ 14. Dashboard.tsx useEffect                    │                          │
      │    - updateHeaders(Authorization)              │                          │
      │    - 复用已配置的 client                        │                          │
      │    - 不重复 configure() ← 关键!                 │                          │
      │                       │                        │                          │
      │ 15. <DashboardPage idOrSlug="1" />             │                          │
      │     GET /api/v1/dashboard/1 ────────────────────────────────────────────>│
      │                       │                        │        16. dashboard JSON │
      │     <────────────────────────────────────────────────────────────────────│
      │                       │                        │                          │
      │ 17. 渲染完成            │                        │                          │
      ▼                       ▼                        ▼                          ▼
```

### 3.2 上下文共享数据流

```
┌──────────────────────────────────────────────────────────────────┐
│  Host App (React State)                                          │
│  ──────────────────                                              │
│   auth:       { token, username, role }                          │
│   themeMode:  'light' | 'dark'                                   │
│   filters:    { country: 'USA', ... }                            │
│   dashboardId: 1 | 2 | 3 | 4                                     │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           │ <MfeContextProvider initialContext={...}>
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  MfeContext (React Context, Module Federation Shared)            │
│  ──────────────────                                              │
│   {                                                               │
│     context: { authToken, themeMode, defaultFilters, ... },     │
│     updateContext: (patch) => void                              │
│   }                                                               │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           │ useMfeContext()
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  SupersetDashboard (MFE Remote Component)                        │
│  ──────────────────                                              │
│   - 读取 authToken → SupersetClient.updateHeaders(Authorization)│
│   - 读取 themeMode → merge(darkThemeOverrides, supersetTheme)   │
│   - 读取 defaultFilters → 注入到 Dashboard 默认参数            │
│   - 渲染 <DashboardPage idOrSlug={dashboardId} />                │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Host App 实现

### 4.1 项目结构

```
mfe-host/
├── package.json
├── tsconfig.json
├── webpack.config.js          # Module Federation Plugin (consumer)
├── public/
│   └── index.html             # 挂载点 #root
└── src/
    ├── index.tsx              # 入口：创建 #app + 加载 bootstrap
    ├── bootstrap.tsx          # 主组件：登录 + 控制面板 + Dashboard 渲染
    └── mfe-types.d.ts         # Module Federation 类型声明
```

### 4.2 webpack.config.js（关键片段）

```javascript
const { ModuleFederationPlugin } = require('webpack').container;
const path = require('path');

module.exports = {
  mode: 'development',
  entry: './src/index.tsx',
  output: {
    publicPath: 'http://localhost:3000/',
    // ...
  },
  resolve: {
    extensions: ['.tsx', '.ts', '.js', '.jsx'],
  },
  module: {
    rules: [
      {
        test: /\.tsx?$/,
        use: 'ts-loader',
        exclude: /node_modules/,
      },
    ],
  },
  plugins: [
    new ModuleFederationPlugin({
      name: 'host',
      remotes: {
        // 关键：定义 superset remote，指向 Superset DevServer
        superset: 'superset@http://localhost:9000/remoteEntry.js',
      },
      shared: {
        // singleton: true 确保 host 和 remote 共享同一个 React 实例
        react: { singleton: true, requiredVersion: deps.react, eager: true },
        'react-dom': { singleton: true, requiredVersion: deps['react-dom'], eager: true },
        'react-router-dom': { singleton: true, requiredVersion: deps['react-router-dom'], eager: true },
        '@emotion/react': { singleton: true, requiredVersion: deps['@emotion/react'], eager: true },
        '@emotion/styled': { singleton: true, requiredVersion: deps['@emotion/styled'], eager: true },
        moment: { singleton: true },
      },
    }),
    new HtmlWebpackPlugin({ template: './public/index.html' }),
  ],
  // 关键：devServer proxy 解决跨域
  devServer: {
    port: 3000,
    historyApiFallback: true,
    hot: true,
    // 把 /api/* 转发到 Superset 后端（8188）
    proxy: [
      {
        context: ['/api'],
        target: 'http://localhost:8188',
        changeOrigin: true,
        ws: true,
      },
    ],
  },
};
```

### 4.3 index.tsx：关键的 #app 元素准备

**根因问题**：Superset 远程模块加载时，`chart-controls` 等 chunk 会在 `preamble.ts` 之前执行顶层 `t()` 调用，触发 Jed 报 `Domain 'undefined' was not found`。

**解决**：在加载任何 Superset 远程模块**之前**（同步代码中），先创建 `#app` 元素并填充 `data-bootstrap`。

```typescript
// mfe-host/src/index.tsx
(() => {
  if (typeof document === 'undefined') return;

  // 创建 #app 元素（与 host 的 #root 不冲突）
  let appEl = document.getElementById('app');
  if (!appEl) {
    appEl = document.createElement('div');
    appEl.id = 'app';
    appEl.style.display = 'none';
    document.body.appendChild(appEl);
  }

  // 关键：填充 data-bootstrap，domain 必须是 'superset'（非空字符串）
  if (!appEl.getAttribute('data-bootstrap')) {
    const MINIMAL_BOOTSTRAP = {
      common: {
        flash_messages: [],
        conf: {},
        locale: 'en',
        feature_flags: {
          EMBEDDED_SUPERSET: true,
          HorizontalFilterBar: true,
        },
        language_pack: {
          domain: 'superset',   // ← 关键！不能是空字符串 ''
          locale_data: {
            superset: {
              '': {
                domain: 'superset',
                lang: 'en',
                plural_forms: 'nplurals=2; plural=(n != 1)',
              },
            },
          },
        },
        extra_categorical_color_schemes: [],
        extra_sequential_color_schemes: [],
        theme_overrides: {},
        menu_data: { menu: [], brand: {}, navbar_right: { show_watermark: false } },
      },
      user: { isActive: true },
    };
    appEl.setAttribute('data-bootstrap', JSON.stringify(MINIMAL_BOOTSTRAP));
  }

  console.log('[MFE Host] #app element with bootstrap data prepared');
})();

// Module Federation requires a dynamic import for the bootstrap
// 这样 shared dependencies (react, react-dom) 可以被异步解析
import('./bootstrap');
```

### 4.4 bootstrap.tsx：登录 + 控制面板 + Dashboard 渲染

**关键代码片段**：

```typescript
// 1. 登录 Superset
async function loginToSuperset(username: string, password: string): Promise<AuthInfo> {
  const resp = await fetch(`${SUPERSET_URL}/api/v1/security/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, provider: 'db', refresh: true }),
  });
  if (!resp.ok) throw new Error(`Login failed (${resp.status}): ${await resp.text()}`);
  const data = await resp.json();
  return { token: data.access_token, username, role: 'Admin' };
}

// 2. 关键：lazy 加载 MfeContext 和 Dashboard
//    这两个模块来自 'superset' remote，通过 Module Federation 异步加载
const MfeContextProvider = lazy(() =>
  import('superset/MfeContext').then(m => ({ default: m.MfeContextProvider })),
);
const SupersetDashboard = lazy(() => import('superset/Dashboard'));

// 3. 渲染：登录后用 MfeContextProvider 包裹 Dashboard
<MfeContextProvider
  initialContext={{
    authToken: auth.token,
    supersetUrl: SUPERSET_URL,
    username: auth.username,
    userRole: auth.role,
    themeMode,         // ← dark/light 状态共享
    defaultFilters: filters,
  }}
>
  <SupersetDashboard
    dashboardId={dashboardId}
    height="100%"
    themeMode={themeMode}
    defaultFilters={filters}
  />
</MfeContextProvider>
```

### 4.5 关键技巧：React 16 事件池化

> **坑点**：React 16 的 SyntheticEvent 是事件池化的。事件回调返回后 `event.target` 会被置为 `null`。如果在 `setState` 的 updater 函数中访问 `e.target.value`，会抛 `Cannot read properties of null`。

**解决**：必须在事件处理器中**同步**提取值：

```typescript
// ❌ 错误
onChange={e => setLoginForm(p => ({ ...p, username: e.target.value }))}

// ✅ 正确
onChange={e => {
  const value = e.target.value;   // 同步提取
  setLoginForm(p => ({ ...p, username: value }));
}}
```

---

## 5. Superset Remote (MFE) 实现

### 5.1 项目结构

```
superset-frontend/src/mfe/
├── Dashboard.tsx           # 主组件（暴露给 host）
├── MfeContext.tsx          # 共享 React Context（暴露给 host）
├── mfePreamble.ts          # MFE 入口预初始化（解决翻译器 domain 问题）
├── ensureBootstrap.ts      # 备用：兜底创建 #app 元素
├── darkTheme.ts            # 暗色主题覆盖
└── types.ts                # 共享类型定义
```

### 5.2 Superset webpack.config.js 关键片段

```javascript
// superset-frontend/webpack.config.js
const { ModuleFederationPlugin } = require('webpack').container;

module.exports = {
  // ...
  plugins: [
    new ModuleFederationPlugin({
      name: 'superset',
      filename: 'remoteEntry.js',
      exposes: {
        // 关键：暴露 Dashboard 和 MfeContext
        './Dashboard': './src/mfe/Dashboard.tsx',
        './MfeContext': './src/mfe/MfeContext.tsx',
      },
      shared: {
        react: { singleton: true, requiredVersion: '16.14.0', eager: true },
        'react-dom': { singleton: true, requiredVersion: '16.14.0', eager: true },
        'react-router-dom': { singleton: true, requiredVersion: '^5.0.0', eager: true },
        '@emotion/react': { singleton: true, requiredVersion: '^11.0.0', eager: true },
        '@emotion/styled': { singleton: true, requiredVersion: '^11.0.0', eager: true },
        moment: { singleton: true },
      },
    }),
  ],
};
```

### 5.3 mfePreamble.ts：解决翻译器 domain 问题（P0）

**根因分析**：

```
┌──────────────────────────────────────────────────────────────────┐
│  标准 Superset SPA 启动流程                                       │
│  ────────────────────────                                        │
│   entry/index.tsx                                                │
│     └─ import './preamble'        ← 先配置翻译器                  │
│         └─ configure({ languagePack })                           │
│         └─ initFeatureFlags(...)                                 │
│         └─ setupClient()                                         │
│     └─ import './App'             ← 再触发其它 chunk 加载         │
│         └─ import chart-controls  ← 顶层 t() 调用安全            │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  MFE 启动流程（出问题）                                            │
│  ─────────────────────                                            │
│   host 加载 'superset/Dashboard'                                 │
│     └─ 解析 Dashboard.tsx 的 import 链                            │
│         ├─ import 'src/views/RootContextProviders'               │
│         │   └─ 内部间接 import 'src/preamble' ← 翻译器在这里     │
│         ├─ import 'src/dashboard/containers/DashboardPage'      │
│         │   └─ 内部 import 'src/dashboard/...'                  │
│         │       └─ import 'packages/superset-ui-chart-controls' │
│         │           └─ 顶层 const X = t('...') ← 顶层 t() 触发!  │
│         │                                                         │
│         问题：webpack 加载顺序不固定，chart-controls              │
│         可能比 preamble 先加载，t() 抛出                          │
│         "Domain `undefined` was not found"                       │
└──────────────────────────────────────────────────────────────────┘
```

**解决方案**：在 `Dashboard.tsx` 的**第一个** side-effect import 是 `mfePreamble.ts`，同步配置翻译器。

```typescript
// superset-frontend/src/mfe/mfePreamble.ts
import { configure, initFeatureFlags, SupersetClient } from '@superset-ui/core';
import moment from 'moment';

// 关键：domain 必须是 'superset'，不能是空字符串 ''
// 原因：Jed 的 textdomain('') 不会设置 _textdomain（因为 !'' === true）
// 后续 t() 调用会抛 "Domain `undefined` was not found"
const DEFAULT_LANGUAGE_PACK = {
  domain: 'superset',
  locale_data: {
    superset: {
      '': {
        domain: 'superset',
        lang: 'en',
        plural_forms: 'nplurals=2; plural=(n != 1)',
      },
    },
  },
};

// 同步配置翻译器
configure({ languagePack: DEFAULT_LANGUAGE_PACK });

// 同步配置 feature flags
initFeatureFlags({
  EMBEDDED_SUPERSET: true,
  HorizontalFilterBar: true,
});

// moment locale
moment.locale('en');

// 标记 MFE 模式
(window as any).__MFE_MODE__ = true;
(window as any).__SupersetClient__ = SupersetClient;

console.log('[MFE Preamble] Translator configured with default language pack');
```

### 5.4 Dashboard.tsx：主组件

**Props 接口**：

```typescript
export interface SupersetDashboardProps {
  dashboardId: number | string;
  height?: string | number;
  authToken?: string;
  supersetUrl?: string;
  themeMode?: 'light' | 'dark';
  themeOverrides?: Record<string, unknown>;
  defaultFilters?: Record<string, unknown>;
  filtersCollapsedByDefault?: boolean;
}
```

**关键实现**：

```typescript
// 1. 第一个 side-effect import：先初始化翻译器
import './mfePreamble';

// 2. 注册所有 Superset chart plugins（关键！不注册则 charts 报 "Item with key X is not registered"）
import setupPlugins from 'src/setup/setupPlugins';
setupPlugins();

// 3. Superset 内部 Provider 链
import { RootContextProviders } from 'src/views/RootContextProviders';

// 4. 关键：用 MemoryRouter 而非 BrowserRouter
//    原因：host 可能已有自己的 BrowserRouter，MemoryRouter 用内存 location 不影响浏览器 URL
import { MemoryRouter as Router } from 'react-router-dom';

// 5. 懒加载 DashboardPage
const DashboardPage = lazy(() =>
  import('src/dashboard/containers/DashboardPage').then(m => ({ default: m.DashboardPage })),
);
```

**核心 useEffect：SupersetClient 初始化（关键：不重复 configure）**：

```typescript
useEffect(() => {
  let cancelled = false;
  const init = async () => {
    // 1. 注册 chart plugins
    setupPlugins();

    // 2. 关键：不重复 configure SupersetClient
    //    根因：configure() 每次会创建新 instance，老 instance 的
    //    in-flight 请求会被中断，浏览器抛 net::ERR_ABORTED
    //
    //    修复：复用 preamble.ts 已经创建好的 Client A
    //    用 updateHeaders() 只更新 Authorization，不创建新 instance
    const isMfeMode = (window as any).__MFE_MODE__;

    if (isMfeMode && (SupersetClient as any).isConfigured()) {
      (SupersetClient as any).updateHeaders({
        Authorization: `Bearer ${authToken}`,
        Accept: 'application/json',
      });
    } else {
      SupersetClient.configure({ /* ... */ });
    }

    // 3. 获取 CSRF token（host 提供 JWT 时）
    try {
      const csrfResp = await fetch(`${hostUrl}/api/v1/security/csrf_token/`, {
        headers: { Authorization: `Bearer ${authToken}` },
        credentials: 'include',
      });
      if (csrfResp.ok) {
        const { result: csrfToken } = await csrfResp.json();
        (SupersetClient as any).updateHeaders({ 'X-CSRFToken': csrfToken });
      }
    } catch (e) { /* GET 请求可能不需要 CSRF */ }

    if (!cancelled) setStatus('ready');
  };
  init();
  return () => { cancelled = true; };
}, [authToken, supersetUrl]);
```

### 5.5 渲染层级

```jsx
<div data-mfe-theme={themeMode} data-mfe-filters-collapsed={...}>
  <Global styles={customizationStyles} />   {/* 暗色模式 + 隐藏菜单 */}
  <MfeToolbar                               {/* 自定义工具栏 */}
    onToggleFilters={() => setFiltersCollapsed(c => !c)}
  />
  <DashboardErrorBoundary isDark={isDark}>
    <Router>                                {/* 关键：Router 在 RootContextProviders 外面 */}
      <RootContextProviders>
        <ThemeProvider theme={mergedTheme}>
          <Suspense fallback={<LoadingOverlay />}>
            <DashboardPage idOrSlug={String(dashboardId)} />
          </Suspense>
        </ThemeProvider>
      </RootContextProviders>
    </Router>
  </DashboardErrorBoundary>
</div>
```

> **关键**：`<Router>` 必须在 `<RootContextProviders>` 外面，因为 `RootContextProviders` 内部的 `QueryParamProvider` 用了 `<Route>`。如果 Router 不在外面，会报 `use <Route> outside a <Router>` 错误。

---

## 6. Webpack Module Federation 配置

### 6.1 共享依赖配置

`shared` 配置必须**完全一致**（singleton、requiredVersion、eager）才能保证 host 和 remote 共享同一份 React 实例。

```javascript
// host 端
shared: {
  react: { singleton: true, requiredVersion: '^16.14.0', eager: true },
  'react-dom': { singleton: true, requiredVersion: '^16.14.0', eager: true },
  // ...
}

// remote 端（Superset）
shared: {
  react: { singleton: true, requiredVersion: '^16.14.0', eager: true },
  'react-dom': { singleton: true, requiredVersion: '^16.14.0', eager: true },
  // ...
}
```

> **坑点**：`eager: true` 是必要的，Superset remote 入口的 `preamble.ts` 在 import 阶段就需要 react，否则会报 `React is not defined`。

### 6.2 跨域问题与 proxy

**问题**：浏览器禁止跨域脚本加载详细错误，导致 `Script error. at handleError`。

**解决**：通过 webpack devServer proxy 把 `/api/*` 转发到 Superset 后端。

```javascript
// mfe-host/webpack.config.js
devServer: {
  proxy: [
    {
      context: ['/api'],
      target: 'http://localhost:8188',
      changeOrigin: true,
    },
  ],
}
```

> **额外**：webpack 的 `output.crossOriginLoading: 'anonymous'` 配合 `crossorigin="anonymous"` script 标签，确保 MFE 资源同源加载，使错误信息不再被屏蔽。

---

## 7. 后端配置 (Superset)

### 7.1 superset_config.py

```python
# superset/superset_config.py

# 启用 CORS（让 host 跨域调用 API）
ENABLE_CORS = True
CORS_OPTIONS = {
    'supports_credentials': True,
    'allow_headers': ['*'],
    'resources': ['*'],
    'origins': ['*'],
}

# 启用 Embedded 模式
FEATURE_FLAGS = {
    "EMBEDDED_SUPERSET": True,
    "HORIZONTAL_FILTER_BAR": True,
    "DASHBOARD_RBAC": True,
    "EMBEDDED_LOGOUT_WINDOW": True,
}

# JWT 配置
JWT_ACCESS_COOKIE_NAME = 'superset_access_token'
JWT_REFRESH_COOKIE_NAME = 'superset_refresh_token'
JWT_ACCESS_CSRF_COOKIE_NAME = 'superset_csrf_token'
JWT_SECRET_KEY = 'your-secret-key-here'

# 公开 dashboard（开发环境）
EMBEDDED_SUPERSET = True
```

### 7.2 数据库权限修复

**问题**：PostgreSQL 数据库中 Admin 角色权限严重缺失（仅 34 个，正常 167+）。

**解决**：

```bash
# 进入 Superset 容器
docker exec -it superset_app bash

# 同步角色权限
superset init
superset fab create-permissions
superset sync-role-definitions

# 或者 Python 脚本
python -c "
from superset import app, security_manager
with app.app_context():
    security_manager.sync_role_definitions()
"
```

---

## 8. 定制化功能

### 8.1 隐藏不需要的菜单项

通过 Emotion `Global` 注入 CSS：

```typescript
const customizationStyles = {
  // 隐藏全局 watermark
  '[class*="watermark"]': { display: 'none !important' },

  // 隐藏 "View query"
  'li[data-menu-id="view_query"]': { display: 'none !important' },

  // 隐藏 "Export"
  'li[data-menu-id="export"]': { display: 'none !important' },

  // 隐藏 "Share dashboard"
  'li[data-menu-id="share_dashboard"]': { display: 'none !important' },

  // 隐藏 "Edit properties"
  'li[data-menu-id="edit_properties"]': { display: 'none !important' },

  // 隐藏 "Refresh dashboard"
  'li[data-menu-id="refresh_dashboard"]': { display: 'none !important' },

  // Filter Bar 折叠
  '[data-mfe-filters-collapsed="true"] [data-test="dashboard-filters-panel"]': {
    display: 'none !important',
  },
};
```

### 8.2 顶部可折叠过滤器

通过 `data-mfe-filters-collapsed` 属性 + `MfeToolbar` 按钮控制：

```jsx
const MfeToolbar = ({ filtersCollapsed, onToggleFilters, dashboardId }) => (
  <div style={{ display: 'flex', alignItems: 'center', ... }}>
    <button onClick={onToggleFilters}>
      <span>{filtersCollapsed ? '▸' : '▾'}</span> Filters
    </button>
    <span>Dashboard #{dashboardId}</span>
  </div>
);

// 主容器
<div data-mfe-filters-collapsed={filtersCollapsed ? 'true' : 'false'}>
```

### 8.3 暗色模式

Superset 4.1 原生不支持暗色模式（`ThemeType` 只有 `'LIGHT'`），通过 `darkTheme.ts` 深度覆盖实现：

```typescript
// darkTheme.ts
export const darkThemeOverrides = {
  colors: {
    text: { label: '#a0b3b8', help: '#8a9a9f' },
    primary: { base: '#3BC0DC', /* ... */ },
    grayscale: {
      base: '#CCCCCC',
      light1: '#3A3A3A',
      light4: '#1A1A1A',
      light5: '#121212',
    },
    // ...
  },
};

// 全局 CSS 覆盖
export const darkModeGlobalStyles = {
  body: { backgroundColor: '#121212 !important', color: '#e0e0e0' },
  '.dashboard-builder': { backgroundColor: '#121212 !important' },
  '.ant-card': { backgroundColor: '#1A1A1A !important' },
  // ...
};
```

合并主题：

```typescript
const mergedTheme = useMemo(() => {
  const overrides = themeMode === 'dark' ? darkThemeOverrides : {};
  return merge({}, supersetTheme, overrides, themeOverrides || {});
}, [themeMode, themeOverrides]);
```

---

## 9. 关键技术问题与解决方案

### 9.1 翻译器 domain 错误（P0）

| 项目 | 内容 |
|---|---|
| **错误** | `Uncaught Error: Domain \`undefined\` was not found` |
| **根因** | `preamble.ts` 中 `language_pack.domain` 是空字符串 `''`，Jed 的 `textdomain('')` 不会设置 `_textdomain`（`!'' === true`）。后续 `t()` 调用时 `_textdomain` 是 `undefined` |
| **解决** | 1. `mfePreamble.ts` 同步配置 `domain: 'superset'`；2. `preamble.ts` 强制 `domain = language_pack.domain || 'superset'` |
| **代码** | 见 5.3 节 |

### 9.2 SupersetClient 重复 configure 导致请求中断（P0）

| 项目 | 内容 |
|---|---|
| **错误** | `net::ERR_ABORTED http://127.0.0.1:3000/api/v1/me/`、`/api/v1/dashboard/1` |
| **根因** | `SupersetClient.configure()` 每次新建 instance，老 instance 的 in-flight 请求被中断 |
| **时序** | 1. `preamble.ts` → `setupClient()` 创建 Client A，触发 CSRF 请求<br>2. `visibilitychange` → `getMe()` 触发 `/me`<br>3. `Dashboard.tsx` `useEffect` → `configure()` 创建 Client B，Client A 的请求被 abort |
| **解决** | 1. 新增 `SupersetClient.updateHeaders(headers)`：只更新 `instance.headers`，不创建新 instance<br>2. 新增 `SupersetClient.isConfigured()`：检查是否已配置<br>3. `Dashboard.tsx` 在 MFE 模式下**复用**已配置的 client，调用 `updateHeaders()` |
| **代码** | `superset-ui-core/src/connection/SupersetClient.ts` |

```typescript
// 新增的非标准 API
(SupersetClient as any).updateHeaders = (headers: Headers) => {
  if (!singletonClient) {
    throw new Error('You must call SupersetClient.configure(...) before calling updateHeaders');
  }
  singletonClient.headers = { ...singletonClient.headers, ...headers };
  return SupersetClient;
};

(SupersetClient as any).isConfigured = () => singletonClient !== undefined;
```

### 9.3 micromark "module is not defined"（P0）

| 项目 | 内容 |
|---|---|
| **错误** | `ReferenceError: module is not defined`（来自 `micromark-extension-gfm-autolink-literal/dev/index.js`） |
| **根因** | 该包的 dev 版本用 `module.exports = ...` 写入 CJS 变量 `module`，浏览器中未定义 |
| **解决** | webpack `NormalModuleReplacementPlugin` 把 `/dev/` 路径替换为 `/lib/` |
| **代码** | `superset-frontend/webpack.config.js` |

```javascript
new webpack.NormalModuleReplacementPlugin(
  /node_modules\/micromark-extension-gfm-autolink-literal\/dev/,
  require.resolve('micromark-extension-gfm-autolink-literal/lib/index.js'),
),
```

### 9.4 跨域 Script error 屏蔽（P0）

| 项目 | 内容 |
|---|---|
| **错误** | `Script error. at handleError (... main.5666610c.js:2114:58)` |
| **根因** | 浏览器对跨域加载的脚本，错误信息被屏蔽（只显示 "Script error."） |
| **解决** | 1. webpack `output.crossOriginLoading: 'anonymous'`<br>2. host dev server proxy 转发 MFE 资源为同源<br>3. `ensureBootstrap.ts` 全局 `error` + `unhandledrejection` 监听，把错误存到 `window.__MFE_ERRORS__` |

### 9.5 CSRF token 403（P0）

| 项目 | 内容 |
|---|---|
| **错误** | POST 请求 403：CSRF token 缺失或无效 |
| **根因** | 使用 JWT Bearer 认证时，仍需 CSRF token |
| **解决** | `Dashboard.tsx` 主动 `fetch('/api/v1/security/csrf_token/')`，获取后用 `updateHeaders({'X-CSRFToken': csrf})` 注入 |

### 9.6 admin 登录无权限（P0）

| 项目 | 内容 |
|---|---|
| **错误** | admin 登录后无任何 dashboard 权限 |
| **根因** | PostgreSQL 数据库中 Admin 角色权限严重缺失（仅 34 个，正常 167+） |
| **解决** | `superset fab create-permissions` + `sync-role-definitions` |

### 9.7 图表插件未注册（P0）

| 项目 | 内容 |
|---|---|
| **错误** | `Error: Item with key "big_number" is not registered` |
| **根因** | MFE 模式直接渲染 `DashboardPage`，未经过 `App.tsx`，未调用 `setupPlugins()` |
| **解决** | `Dashboard.tsx` 的 `init()` 中显式调用 `setupPlugins()` |

### 9.8 underscore-esm ESM 解析错误（P1）

| 项目 | 内容 |
|---|---|
| **错误** | `Module parse failed: 'import' and 'export' may appear only with 'sourceType: module'` |
| **根因** | `underscore-esm.js` 是 ESM 语法但 package.json 没有 `"type": "module"` |
| **解决** | babel-loader 用 `sourceType: 'unambiguous'` + `modules: 'commonjs'` |

### 9.9 React 16 事件池化（P1）

| 项目 | 内容 |
|---|---|
| **错误** | `Cannot read properties of null (reading 'value')` |
| **根因** | React 16 的 SyntheticEvent 事件池化，回调后 `event.target` 被置为 null |
| **解决** | 在事件处理器中**同步**提取 `e.target.value` |

### 9.10 React key 警告（P1）

| 项目 | 内容 |
|---|---|
| **警告** | `Warning: Each child in a list should have a unique "key" prop` |
| **根因** | `Header` 组件的 `titlePanelAdditionalItems` 数组可能包含 `null/false` |
| **解决** | `PageHeaderWithActions` 中用 `React.Children.toArray()` 包装 |

### 9.11 WorldMap formatter 类型错误（P1）

| 项目 | 内容 |
|---|---|
| **警告** | `Invalid prop \`formatter\` of type \`function\` supplied to \`WorldMap\`, expected \`object\`` |
| **根因** | `formatter` propTypes 定义为 object，但实际传入 `NumberFormatter`（可调用对象） |
| **解决** | 修改 `propTypes: PropTypes.oneOfType([PropTypes.object, PropTypes.func])` |

### 9.12 Function components cannot be given refs（P1）

| 项目 | 内容 |
|---|---|
| **警告** | `Function components cannot be given refs` |
| **根因** | `Button` 组件没用 `React.forwardRef` |
| **解决** | `Button` 用 `forwardRef` 包装，将 `ref` 传给 `AntdButton` |

### 9.13 antd _interopRequireDefault 错误（P0）

| 项目 | 内容 |
|---|---|
| **错误** | `TypeError: _interopRequireDefault is not a function` |
| **根因** | antd 依赖 `@babel/runtime/helpers/interopRequireDefault`，webpack 解析为 ESM 版本，CJS 环境下无法直接调用 |
| **解决** | webpack `resolve.conditionNames` 优先 `['node', 'require']`，确保 CJS 模块正确加载 |

### 9.14 emotion :first-child SSR 警告（P2）

| 项目 | 内容 |
|---|---|
| **警告** | `emotion: The pseudo class ":first-child" is potentially unsafe when doing server-side rendering` |
| **根因** | emotion 11 的 SSR 警告，不影响功能 |
| **解决** | 暂时忽略（不影响功能） |

### 9.15 componentWillMount 警告（P2）

| 项目 | 内容 |
|---|---|
| **警告** | `componentWillMount has been renamed, and is not recommended for use` |
| **根因** | `CustomLoadableRenderer` 内部使用 `componentWillMount` |
| **解决** | 暂时忽略（Superset 4.1 内部组件） |

### 9.16 ECharts DOM 0 警告（P2）

| 项目 | 内容 |
|---|---|
| **警告** | `ECharts: There is a chart instance already initialized on the dom` |
| **根因** | 容器尺寸为 0 时 ECharts 报错 |
| **解决** | 确保 MFE 容器有明确 `height` |

---

## 10. 调试与回归测试清单

### 10.1 必跑测试场景

| # | 场景 | 操作 | 预期 |
|---|---|---|---|
| 1 | 初次加载 dashboard 1 | 选择 World Bank's Data | 渲染 5-10 个 charts，无 console error |
| 2 | 切换 dashboard 3 | 选 Misc Charts | ECharts 正常显示，URL 切换 |
| 3 | 切换 dashboard 4 | 选 deck.gl Demo | 地图正常加载 |
| 4 | Filter 折叠 | 点 ▾ → ▸ | Filter bar 隐藏，按钮状态正确 |
| 5 | Filter 展开 | 再点 ▸ → ▾ | Filter bar 显示 |
| 6 | 添加过滤器 | 输入 country=USA | Dashboard 重新查询数据 |
| 7 | 清除过滤器 | 点 × | 过滤器移除，dashboard 重新查询 |
| 8 | 暗色模式 | 点 🌙 | 整个 dashboard 切到暗色，无白边 |
| 9 | 亮色模式 | 点 ☀️ | 切回亮色 |
| 10 | 登出 | 点登出 | 返回登录页 |
| 11 | 重新登录 | 输 admin/admin | 重新进入 dashboard，token 更新 |
| 12 | 刷新页面 | F5 | 自动从 cookie 恢复登录状态 |
| 13 | 跨标签页测试 | 打开两个 tab | 各自独立，共享同一 token |
| 14 | 暗色 + filter 折叠 | 切暗色 + 折叠 filter | 工具栏和 chart 都正确显示 |

### 10.2 Console Error 监控

**不应该出现**：
- ❌ `Domain 'undefined' was not found`
- ❌ `net::ERR_ABORTED` (请求中断)
- ❌ `Item with key "X" is not registered`
- ❌ `_interopRequireDefault is not a function`
- ❌ `module is not defined` (micromark)
- ❌ `Script error.` (跨域)

**可以接受**（已知警告）：
- ⚠️ `emotion: The pseudo class ":first-child" is potentially unsafe...`
- ⚠️ `componentWillMount has been renamed...`

---

## 11. 启动流程

### 11.1 启动顺序

```bash
# 1. 启动 Docker 数据库
cd docker
docker-compose up -d postgres redis

# 2. 启动 Superset 后端
cd ..
superset run -p 8188 --with-threads --reload --debugger

# 3. 启动 Superset 前端 Dev Server (MFE Remote)
cd superset-frontend
npm run dev-server
# 启动后访问 http://localhost:9000/remoteEntry.js 应返回 JS

# 4. 启动 Host App
cd ../../mfe-host
npm start
# 访问 http://localhost:3000
```

### 11.2 验证清单

```bash
# 检查 Superset 后端
curl http://localhost:8188/api/v1/security/csrf_token/ -I

# 检查 Superset Dev Server
curl http://localhost:9000/remoteEntry.js -I

# 检查 Host App
curl http://localhost:3000/ -I

# 登录测试
curl -X POST http://localhost:8188/api/v1/security/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin","provider":"db","refresh":true}'
```

---

## 12. 待办与未来工作

### 12.1 待办 (Pending)

- [ ] 修复 Row/Column `onResize`/`maxChildrenHeight` 警告
- [ ] 修复 `Item with key '+,' already exists` 警告（formatRegistry 重复注册）
- [ ] 修复 `Chart timeout/maxRows` 警告
- [ ] 完整回归测试：dashboard 1/3/4 + filter 折叠 + 暗色模式
- [ ] 修复 `emotion :first-child` SSR 警告
- [ ] 修复 `componentWillMount` 警告（CustomLoadableRenderer）
- [ ] 修复 ECharts DOM 0 警告（容器尺寸问题）

### 12.2 未来工作

- [ ] 生产环境构建配置（去除 dev tooling）
- [ ] 性能优化：lazy load chart plugins
- [ ] 错误上报集成（Sentry）
- [ ] 主题自定义 API
- [ ] 权限过滤：让 host 控制 dashboard 可见性
- [ ] Guest Token 模式（替代 JWT）

---

## 附录 A：关键文件清单

| 文件 | 作用 |
|---|---|
| `mfe-host/src/index.tsx` | Host 入口，同步创建 #app 元素 |
| `mfe-host/src/bootstrap.tsx` | Host 主组件，登录 + 控制面板 |
| `mfe-host/webpack.config.js` | Host Module Federation 配置 + proxy |
| `superset-frontend/src/mfe/Dashboard.tsx` | MFE 主组件 |
| `superset-frontend/src/mfe/mfePreamble.ts` | MFE 翻译器预初始化 |
| `superset-frontend/src/mfe/MfeContext.tsx` | 共享 React Context |
| `superset-frontend/src/mfe/darkTheme.ts` | 暗色主题覆盖 |
| `superset-frontend/src/mfe/ensureBootstrap.ts` | 兜底创建 #app 元素 + 错误捕获 |
| `superset-frontend/src/preamble.ts` | 修复 `domain = language_pack.domain \|\| 'superset'` |
| `superset-frontend/webpack.config.js` | Superset MF 配置 + micromark 修复 |
| `superset-frontend/packages/superset-ui-core/src/connection/SupersetClient.ts` | 新增 `updateHeaders` / `isConfigured` |
| `superset-frontend/packages/superset-ui-core/src/connection/SupersetClientClass.ts` | (只读参考) |
| `superset-frontend/src/setup/setupClient.ts` | (只读参考) |
| `superset-frontend/src/views/RootContextProviders.tsx` | Superset Provider 链 |
| `superset-frontend/src/setup/setupPlugins.ts` | 注册所有 chart plugins |
| `superset-frontend/src/components/PageHeaderWithActions/index.tsx` | 修复 key 警告 |
| `superset-frontend/src/components/Button/index.tsx` | forwardRef 修复 |
| `superset-frontend/src/dashboard/components/DashboardGrid.jsx` | 修复 Row onResize |
| `superset-frontend/plugins/legacy-plugin-chart-world-map/src/WorldMap.js` | 修复 formatter propTypes |
| `superset/superset_config.py` | CORS + JWT + feature flags 配置 |

## 附录 B：常用命令

```bash
# 重新构建 Superset 前端
cd superset-frontend
npm run build
npm run dev-server

# 重启 Host
cd mfe-host
npm start

# 查看 Superset 日志
docker logs -f superset_app

# 同步角色权限
docker exec -it superset_app superset sync-role-definitions

# 重置数据库
docker exec -it superset_app superset db upgrade
docker exec -it superset_app superset init
```
