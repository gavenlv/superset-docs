# Superset 4.1 源码启动 + Module Federation MFE 上下文共享实现文档

> 本文档记录了从源码启动 Apache Superset 4.1，并通过 Webpack Module Federation 实现 Host App 与 Superset Dashboard 的**原生组件集成**（非 iframe），支持**认证、主题、过滤器上下文共享**的完整实现流程。

---

## 架构概览

```
┌───────────────────────────────────────────────────────────────────────┐
│  浏览器                                                                │
│                                                                        │
│  ┌────────────────────────────────┐    ┌────────────────────────────┐ │
│  │  Host App (port 3000)          │    │  Superset Dev Server (9000)│ │
│  │  ──────────────────────────    │    │  ────────────────────────  │ │
│  │  React 16.14.0                 │    │  Webpack 5 + Dev Server    │ │
│  │  ModuleFederationPlugin       │───>│  ModuleFederationPlugin    │ │
│  │  remotes:                      │    │  name: 'superset'          │ │
│  │    superset@...:9000/...      │    │  exposes:                  │ │
│  │                                │    │    ./Dashboard              │ │
│  │  功能:                          │    │    ./MfeContext             │ │
│  │   ✓ 登录 UI (admin/admin)     │    │  shared (singleton):        │ │
│  │   ✓ Dark/Light 主题切换        │    │    react, react-dom         │ │
│  │   ✓ 过滤器控件                 │    │    @emotion/react           │ │
│  │   ✓ Dashboard 选择器           │    │    react-router-dom         │ │
│  │                                │    │  remoteEntry.js (634KB)    │ │
│  │  <MfeContextProvider>         │    │                            │ │
│  │    └─ <SupersetDashboard>     │    │  MFE 组件:                  │ │
│  │         (原生 React 组件)      │    │   Dashboard.tsx            │ │
│  │         非 iframe 嵌入         │    │   MfeContext.tsx            │ │
│  └──────────┬─────────────────────┘    └────────────────────────────┘ │
│             │                                          │              │
│             │ JWT Token (Authorization: Bearer ...)    │              │
│             │ ────────────────────────────────────────>│              │
│             │                                          │ proxy        │
│             ▼                                          ▼              │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │  Superset Backend (port 8188)                                    ││
│  │  ──────────────────────────────────────                          ││
│  │  Flask + Flask-AppBuilder (FAB 4.5.0)                           ││
│  │  REST API:                                                      ││
│  │    POST /api/v1/security/login → { access_token }              ││
│  │    GET  /api/v1/dashboard/{id}  → dashboard metadata          ││
│  │    GET  /api/v1/csrf_token/     → CSRF token                   ││
│  │  FEATURE_FLAGS: { EMBEDDED_SUPERSET: true }                    ││
│  └──────────┬───────────────────────────────────┬────────────────────┘│
│             │                                   │                     │
│             ▼                                   ▼                     │
│  ┌────────────────────┐              ┌────────────────────┐           │
│  │  Docker PostgreSQL │              │  Docker Redis      │           │
│  │  port 15435        │              │  port 16382        │           │
│  │  superset DB       │              │  DB 1-5 (cache,    │           │
│  │  (metadata +       │              │    session, celery)│           │
│  │   examples data)   │              │                    │           │
│  └────────────────────┘              └────────────────────┘           │
└───────────────────────────────────────────────────────────────────────┘
```

### 上下文共享架构（核心）

```
┌─────────────────────────────────────────────────────────────────────┐
│  MFE 上下文共享 (通过 Module Federation 共享 MfeContext)             │
│                                                                      │
│  ┌──────────────┐                    ┌──────────────────────────┐     │
│  │  Host App    │                    │  Superset Remote        │     │
│  │              │                    │                         │     │
│  │  1. 认证共享  │ ──authToken──>    │  SupersetClient.configure│    │
│  │  登录获取 JWT │                    │  ({ headers: {           │     │
│  │  传入 Context │                    │     Authorization:       │     │
│  │              │                    │       Bearer <token> }}) │     │
│  │              │                    │                         │     │
│  │  2. 主题共享  │ ──themeMode──>    │  buildMergedTheme()     │     │
│  │  dark/light  │                    │  merge(supersetTheme,   │     │
│  │  切换 UI     │                    │    darkThemeOverrides,   │     │
│  │              │                    │    hostOverrides)       │     │
│  │              │                    │  <ThemeProvider theme=>  │     │
│  │              │                    │                         │     │
│  │  3. 过滤器共享 │ ─defaultFilters─>│  CustomEvent            │     │
│  │  控件设置     │                    │  mfe:filterUpdate       │     │
│  │  过滤器参数   │                    │  → Dashboard 联动       │     │
│  └──────────────┘                    └──────────────────────────┘     │
│                                                                      │
│  共享机制: 同一个 React Context 实例 (通过 Module Federation 共享)    │
│  Host 和 Remote 都 import 同一个 MfeContext → 同一个 Context 对象    │
└─────────────────────────────────────────────────────────────────────┘
```

### 端口分配

| 服务              | 端口  | 说明                        |
| ----------------- | ----- | --------------------------- |
| Docker PostgreSQL | 15435 | 避开宿主机 5432             |
| Docker Redis      | 16382 | 避开其他 Redis 实例         |
| Superset Backend  | 8188  | 避开 Jenkins 占用的 8088    |
| Superset Frontend | 9000  | webpack-dev-server (remote) |
| Host App          | 3000  | 测试 MFE 消费 (host)        |

---

## 实现步骤

### 第 1 步：启动 Docker 容器（PostgreSQL + Redis）

```bash
# PostgreSQL 15 (metadata + examples data)
docker run -d --name superset-src-postgres \
  -e POSTGRES_USER=superset \
  -e POSTGRES_PASSWORD=superset \
  -e POSTGRES_DB=superset \
  -p 15435:5432 \
  postgres:15

# Redis 7 (cache + session + celery broker)
docker run -d --name superset-src-redis \
  -p 16382:6379 \
  redis:7
```

---

### 第 2 步：配置 superset_config.py

关键配置项（详见 [superset_config.py](file:///d:/workspace/superset-space/superset-github/superset-4.1-token/superset_config.py)）：

```python
from superset.config import *

# 1. 数据库 - Docker PostgreSQL
SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://superset:superset@localhost:15435/superset"
SQLALCHEMY_EXAMPLES_URI = "postgresql+psycopg2://superset:superset@localhost:15435/superset"

# 2. 缓存 / Session / Celery - Docker Redis
CACHE_CONFIG = { 'CACHE_REDIS_URL': 'redis://localhost:16382/1', ... }
DATA_CACHE_CONFIG = { 'CACHE_REDIS_URL': 'redis://localhost:16382/2', ... }
CELERY_CONFIG = { 'broker_url': 'redis://localhost:16382/3', ... }
SESSION_TYPE = 'redis'
SESSION_REDIS_URL = 'redis://localhost:16382/5'

# 3. CORS - 允许 host app (3000) 跨域访问 API
ENABLE_CORS = True
CORS_OPTIONS = {
    'origins': ['http://localhost:3000', 'http://localhost:9000', ...],
    'supports_credentials': True,
    'allow_headers': ['*'],
}

# 4. 启用嵌入式 Superset 特性 (MFE 组件需要)
FEATURE_FLAGS = { 'EMBEDDED_SUPERSET': True }

# 5. Guest token 配置 (可选,用于嵌入式场景)
GUEST_TOKEN_JWT_SECRET = SECRET_KEY
GUEST_TOKEN_JWT_AUDIENCE = 'superset.embedded_jwt'
```

> **注意**：由于本方案使用原生 React 组件集成（非 iframe），CSP `frame-ancestors` 配置不再是必需的。但保留它不影响功能。

---

### 第 3 步：初始化后端数据库 + 创建管理员 + 导入示例数据

```bat
set PYTHONPATH=d:\workspace\superset-space\superset-github\superset-4.1-token
set SUPERSET_CONFIG_PATH=...\superset_config.py
set FLASK_APP=superset.app:create_app()

REM 1. 数据库迁移
venv\Scripts\python.exe -m flask db upgrade

REM 2. 创建 admin 用户 (admin/admin)
venv\Scripts\python.exe -m flask fab create-admin --username admin --firstname Superset --lastname Admin --email admin@superset.com --password admin

REM 3. 同步角色权限（重要！否则 API 返回 403 Forbidden）
venv\Scripts\python.exe -m flask superset init

REM 4. 导入示例数据
venv\Scripts\python.exe -m flask superset load_examples
```

**已加载的示例 Dashboard：**
- ID=1: World Bank's Data
- ID=2: USA Births Names
- ID=3: Misc Charts
- ID=4: deck.gl Demo

---

### 第 4 步：启动后端

```bat
@echo off
set PYTHONPATH=d:\workspace\superset-space\superset-github\superset-4.1-token
set SUPERSET_SECRET_KEY=3Kotb6M3aKK89WAQdnog7T4QPUFpMGs5mJdgUp9jflTtJUO_Eb6HX-0i
set SUPERSET_CONFIG_PATH=...\superset_config.py
set FLASK_ENV=development
set FLASK_APP=superset.app:create_app()
venv\Scripts\python.exe -m flask run -p 8188 --with-threads --reload --debugger
```

---

### 第 5 步：配置 Module Federation（暴露 Dashboard + MfeContext）

#### 5.1 修改 `superset-frontend/webpack.config.js`

```javascript
const { ModuleFederationPlugin } = require('webpack').container;

new ModuleFederationPlugin({
  name: 'superset',
  filename: 'remoteEntry.js',
  exposes: {
    // 暴露 Dashboard 组件 (原生 React 组件,非 iframe)
    './Dashboard': './src/mfe/Dashboard.tsx',
    // 暴露 MfeContext 让 host app 使用同一个 Context 实例
    './MfeContext': './src/mfe/MfeContext.tsx',
  },
  shared: {
    // React 必须是 singleton
    react: { singleton: true, eager: false, requiredVersion: '^16.14.0' },
    'react-dom': { singleton: true, eager: false, requiredVersion: '^16.14.0' },
    // @emotion/react 共享 - 确保主题在 host 和 remote 之间一致
    '@emotion/react': { singleton: true, eager: false, requiredVersion: '^11.0.0' },
    // react-router-dom 共享 - DashboardPage 内部使用 useHistory
    'react-router-dom': { singleton: true, eager: false, requiredVersion: '^5.3.0' },
  },
}),
```

#### 5.2 创建 MFE 模块文件

**`superset-frontend/src/mfe/types.ts`** - 共享类型定义：

```typescript
export type ThemeMode = 'light' | 'dark';

export interface MfeSharedContext {
  // 认证上下文
  authToken: string;           // Superset JWT access token
  supersetUrl: string;         // 后端 URL
  username?: string;
  userRole?: string;
  // 主题上下文
  themeMode: ThemeMode;        // 'light' | 'dark'
  themeOverrides?: Record<string, unknown>;
  // 过滤器上下文
  defaultFilters?: FilterValues;
  onFiltersChange?: (filters: FilterValues) => void;
}

export interface MfeContextType {
  context: MfeSharedContext;
  updateContext: (patch: Partial<MfeSharedContext>) => void;
}
```

**`superset-frontend/src/mfe/MfeContext.tsx`** - 共享 React Context：

```typescript
import React, { createContext, useContext, useState, useCallback } from 'react';
import type { MfeSharedContext, MfeContextType } from './types';

// 通过 Module Federation 共享 → host 和 remote 使用同一个 Context 实例
export const MfeContext = createContext<MfeContextType>({ ... });

export const MfeContextProvider: React.FC<{
  initialContext?: Partial<MfeSharedContext>;
  children: React.ReactNode;
}> = ({ initialContext, children }) => {
  const [context, setContext] = useState<MfeSharedContext>({
    ...defaultContext,
    ...initialContext,
  });
  const updateContext = useCallback((patch) => {
    setContext(prev => ({ ...prev, ...patch }));
  }, []);
  return <MfeContext.Provider value={{ context, updateContext }}>{children}</MfeContext.Provider>;
};

export const useMfeContext = (): MfeContextType => useContext(MfeContext);
```

**`superset-frontend/src/mfe/darkTheme.ts`** - 暗色主题覆盖：

```typescript
// Superset 4.1 不原生支持 dark mode (ThemeType 仅有 LIGHT)
// 通过 deep-merge 覆盖 supersetTheme 的颜色值
export const darkThemeOverrides = {
  colors: {
    text: { label: '#a0b3b8', help: '#8a9a9f' },
    primary: { base: '#3BC0DC', light3: '#1A3A45', ... },
    secondary: { base: '#6B75A4', light3: '#2A2F45', ... },
    grayscale: { base: '#CCCCCC', dark1: '#E0E0E0', light2: '#2A2A2A', light5: '#121212', ... },
    error: { base: '#FF6B7A', ... },
    warning: { base: '#FF9266', ... },
    success: { base: '#6BD89F', ... },
    info: { base: '#7BC8FE', ... },
  },
};

// Emotion Global CSS - 覆盖硬编码的白色背景
export const darkModeGlobalStyles = {
  body: { backgroundColor: '#121212 !important', color: '#e0e0e0' },
  '.dashboard .dashboard-component-tabs': { backgroundColor: '#1A1A1A !important' },
  '.ant-card': { backgroundColor: '#1A1A1A !important', ... },
  '.ant-table': { backgroundColor: '#1A1A1A !important' },
  ...
};
```

**`superset-frontend/src/mfe/Dashboard.tsx`** - 核心 MFE 组件：

```typescript
import React, { useEffect, useState, useMemo, lazy, Suspense } from 'react';
import { Global } from '@emotion/react';
import { merge } from 'lodash';
import { SupersetClient, supersetTheme, ThemeProvider } from '@superset-ui/core';
import { useMfeContext } from './MfeContext';
import { darkThemeOverrides, darkModeGlobalStyles } from './darkTheme';
import { RootContextProviders } from 'src/views/RootContextProviders';
import { BrowserRouter as Router, Route } from 'react-router-dom';

// 懒加载 DashboardPage
const DashboardPage = lazy(() =>
  import('src/dashboard/containers/DashboardPage').then(m => ({ default: m.DashboardPage })),
);

export interface SupersetDashboardProps {
  dashboardId: number | string;
  height?: string | number;
  authToken?: string;
  supersetUrl?: string;
  themeMode?: 'light' | 'dark';
  themeOverrides?: Record<string, unknown>;
  defaultFilters?: Record<string, unknown>;
}

export const SupersetDashboard: React.FC<SupersetDashboardProps> = (props) => {
  // 1. 从 MFE 共享 Context 读取 host app 提供的上下文
  const { context } = useMfeContext();
  const authToken = props.authToken || context.authToken;
  const themeMode = props.themeMode || context.themeMode || 'light';
  // ...合并 props 和 context

  // 2. 构建合并后的主题 (supersetTheme + dark overrides + host overrides)
  const mergedTheme = useMemo(
    () => merge({}, supersetTheme, themeMode === 'dark' ? darkThemeOverrides : {}, ...),
    [themeMode, themeOverrides],
  );

  // 3. 初始化: 配置 SupersetClient + 注入 bootstrap data
  useEffect(() => {
    ensureBootstrapData();  // 创建 #app div with data-bootstrap
    SupersetClient.configure({
      host: url.host,
      protocol: url.protocol,
      headers: { Authorization: `Bearer ${authToken}` },
      mode: 'cors',
      credentials: 'include',
    });
    await SupersetClient.init();  // 获取 CSRF token
    setStatus('ready');
  }, [authToken, supersetUrl]);

  // 4. 监听过滤器变化 (host → dashboard 联动)
  useEffect(() => {
    window.dispatchEvent(new CustomEvent('mfe:filterUpdate', { detail: defaultFilters }));
  }, [defaultFilters]);

  // 5. 渲染原生 Dashboard (非 iframe)
  return (
    <div data-mfe-theme={themeMode}>
      {isDark && <Global styles={darkModeGlobalStyles} />}
      <RootContextProviders>
        <ThemeProvider theme={mergedTheme}>
          <Router>
            <Route>
              <Suspense fallback={<LoadingOverlay />}>
                <DashboardPage idOrSlug={String(dashboardId)} />
              </Suspense>
            </Route>
          </Router>
        </ThemeProvider>
      </RootContextProviders>
    </div>
  );
};
```

#### 5.3 关键设计点

1. **ensureBootstrapData()** — Superset 的 `getBootstrapData()` 从 `#app` 元素的 `data-bootstrap` 属性读取数据。MFE 场景下 host app 的 HTML 没有这个数据，需要手动注入最小化的 bootstrap JSON。

2. **SupersetClient.configure()** — 使用 host app 提供的 JWT token 重新配置单例 SupersetClient，所有后续 API 调用自动带上 `Authorization: Bearer <token>` header。

3. **RootContextProviders** — Superset 的 Provider 链：ThemeProvider → AntdThemeProvider → ReduxProvider → DndProvider → FlashProvider → EmbeddedUiConfigProvider → DynamicPluginProvider → QueryParamProvider。提供 DashboardPage 所需的所有上下文。

4. **ThemeProvider 覆盖** — 在 RootContextProviders 内部包裹一个 `<ThemeProvider theme={mergedTheme}>`，使 DashboardPage 子树使用合并后的主题（包含 dark overrides）。

5. **lazy 加载 DashboardPage** — DashboardPage 是一个很大的组件（包含 Redux hooks、useDashboard、useHistory 等），通过 `React.lazy()` 懒加载，避免初始 bundle 过大。

---

### 第 6 步：修复 npm workspace 符号链接（重要！）

**问题**：项目移动路径后，npm workspace 创建的符号链接全部断开，导致 652 个编译错误。

**修复**：批量重建 27 个 `@superset-ui/*` 符号链接 + 2 个 eslint-plugin 链接。

```bash
cd superset-frontend/node_modules/@superset-ui
for link in chart-controls core demo generator-superset \
           legacy-plugin-chart-* legacy-preset-chart-* \
           plugin-chart-* switchboard; do
  target=$(readlink "$link")
  new_target="${target/\/old\/path/\/new\/path}"
  rm -rf "$link" && ln -s "$new_target" "$link"
done
```

---

### 第 7 步：启动前端 dev server

```bat
@echo off
cd /d d:\workspace\superset-space\superset-github\superset-4.1-token\superset-frontend
npx cross-env NODE_ENV=development BABEL_ENV=development ^
  node --max_old_space_size=4096 ^
  ./node_modules/webpack-dev-server/bin/webpack-dev-server.js ^
  --mode=development --env=--supersetPort=8188
```

验证 remoteEntry.js 包含 MfeContext 暴露：
```bash
curl -s http://localhost:9000/static/assets/remoteEntry.js | grep "MfeContext"
# 应找到 MfeContext
```

---

### 第 8 步：创建 Host App

#### 8.1 `mfe-host/package.json`

```json
{
  "name": "mfe-host",
  "version": "1.0.0",
  "dependencies": {
    "react": "16.14.0",
    "react-dom": "16.14.0",
    "@emotion/react": "^11.11.0",
    "react-router-dom": "^5.3.0"
  },
  "devDependencies": {
    "@babel/core": "^7.23.0",
    "@babel/preset-env": "^7.23.0",
    "@babel/preset-react": "^7.22.0",
    "@babel/preset-typescript": "^7.23.0",
    "babel-loader": "^9.1.3",
    "css-loader": "^6.8.0",
    "html-webpack-plugin": "^5.5.0",
    "style-loader": "^3.3.0",
    "typescript": "^5.2.0",
    "webpack": "^5.89.0",
    "webpack-cli": "^5.1.0",
    "webpack-dev-server": "^4.15.0"
  }
}
```

> **关键**：`@emotion/react` 和 `react-router-dom` 版本必须与 Superset 一致，且作为 singleton 共享。

#### 8.2 `mfe-host/webpack.config.js`

```javascript
const { ModuleFederationPlugin } = require('webpack').container;
const HtmlWebpackPlugin = require('html-webpack-plugin');
const deps = require('./package.json').dependencies;

module.exports = {
  entry: './src/index.tsx',
  mode: 'development',
  devServer: {
    port: 3000,
    headers: { 'Access-Control-Allow-Origin': '*', ... },
  },
  output: { publicPath: 'http://localhost:3000/' },
  plugins: [
    new ModuleFederationPlugin({
      name: 'host',
      remotes: {
        superset: 'superset@http://localhost:9000/static/assets/remoteEntry.js',
      },
      shared: {
        react: { singleton: true, requiredVersion: deps.react, eager: false },
        'react-dom': { singleton: true, requiredVersion: deps['react-dom'], eager: false },
        '@emotion/react': { singleton: true, requiredVersion: deps['@emotion/react'], eager: false },
        'react-router-dom': { singleton: true, requiredVersion: deps['react-router-dom'], eager: false },
      },
    }),
    new HtmlWebpackPlugin({ template: './public/index.html' }),
  ],
};
```

#### 8.3 `mfe-host/src/index.tsx`（异步入口，必需！）

```typescript
// Module Federation 要求：必须使用动态 import 加载 bootstrap
import('./bootstrap');
```

#### 8.4 `mfe-host/src/bootstrap.tsx`（主应用）

Host app 实现了完整的上下文共享 UI：

```typescript
import React, { Suspense, lazy, useState, useCallback } from 'react';
import ReactDOM from 'react-dom';

// 从 Superset remote 导入 MfeContext (共享 Context 实例)
const MfeContextProvider = lazy(() =>
  import('superset/MfeContext').then(m => ({ default: m.MfeContextProvider })),
);

// 从 Superset remote 导入 Dashboard 组件
const SupersetDashboard = lazy(() => import('superset/Dashboard'));

// === 1. 认证: 登录到 Superset API 获取 JWT ===
async function loginToSuperset(username, password): Promise<AuthInfo> {
  const resp = await fetch(`${SUPERSET_URL}/api/v1/security/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, provider: 'db', refresh: true }),
  });
  const data = await resp.json();
  return { token: data.access_token, username, role: 'Admin' };
}

// === 2. 主组件 ===
const App: React.FC = () => {
  const [auth, setAuth] = useState<AuthInfo | null>(null);
  const [themeMode, setThemeMode] = useState<'light' | 'dark'>('light');
  const [dashboardId, setDashboardId] = useState<number>(1);
  const [filters, setFilters] = useState<Record<string, unknown>>({});

  if (!auth) {
    // 登录页面 (带主题切换)
    return <LoginForm onLogin={...} themeMode={themeMode} ... />;
  }

  // 已登录 - 主界面
  return (
    <div>
      <Header user={auth} themeMode={themeMode} onToggleTheme={...} onLogout={...} />
      <ControlPanel
        dashboardId={dashboardId} onDashboardChange={...}
        filters={filters} onAddFilter={...} onClearFilters={...}
        themeMode={themeMode} auth={auth}
      />
      {/* Dashboard 渲染区 - 使用 MfeContextProvider 包裹 */}
      <Suspense fallback={<Loading />}>
        <MfeContextProvider
          initialContext={{
            authToken: auth.token,        // ← 认证共享
            supersetUrl: SUPERSET_URL,
            username: auth.username,
            userRole: auth.role,
            themeMode,                     // ← 主题共享
            defaultFilters: filters,       // ← 过滤器共享
          }}
        >
          <SupersetDashboard
            dashboardId={dashboardId}
            height="100%"
            themeMode={themeMode}
            defaultFilters={filters}
          />
        </MfeContextProvider>
      </Suspense>
    </div>
  );
};
```

#### 8.5 `mfe-host/src/mfe-types.d.ts`（TypeScript 声明）

```typescript
declare module 'superset/Dashboard' {
  export interface SupersetDashboardProps {
    dashboardId: number | string;
    height?: string | number;
    authToken?: string;
    supersetUrl?: string;
    themeMode?: 'light' | 'dark';
    themeOverrides?: Record<string, unknown>;
    defaultFilters?: Record<string, unknown>;
  }
  export const SupersetDashboard: React.FC<SupersetDashboardProps>;
  const _default: typeof SupersetDashboard;
  export default _default;
}

declare module 'superset/MfeContext' {
  export interface MfeSharedContext { ... }
  export interface MfeContextType { ... }
  export const MfeContext: React.Context<MfeContextType>;
  export const MfeContextProvider: React.FC<{ ... }>;
  export const useMfeContext: () => MfeContextType;
}
```

---

## 启动顺序（重要！）

```
1. Docker 容器（PostgreSQL + Redis）
   ↓
2. 后端（flask run, port 8188）
   ↓
3. 前端 dev server（webpack-dev-server, port 9000）
   ↓  生成 remoteEntry.js (含 ./Dashboard + ./MfeContext)
   ↓
4. Host App（webpack serve, port 3000）
   ↓  加载 remoteEntry.js
   ↓
5. 访问 http://localhost:3000 测试
   ↓  登录 admin/admin → 选择 Dashboard → 切换主题 → 添加过滤器
```

---

## 上下文共享详解

### 1. 认证上下文共享

```
Host App                        Superset Remote
────────                        ───────────────
用户输入用户名密码
    ↓
POST /api/v1/security/login
    ↓
获取 access_token (JWT)
    ↓
存入 React State
    ↓
<MfeContextProvider
  initialContext={{
    authToken: access_token   ───→  useMfeContext().context.authToken
  }}                                  ↓
>                                    SupersetClient.configure({
>                                      headers: {
>                                        Authorization:
>                                          `Bearer ${authToken}`
>                                      }
>                                    })
>                                    ↓
>                                    所有 API 调用自动带 JWT
>                                    GET /api/v1/dashboard/{id} ✓
>                                    POST /api/v1/chart/data  ✓
```

**关键**：Host app 登录后，JWT token 通过 MfeContext 传给 Superset 组件，Superset 组件用它配置 SupersetClient 单例，所有后续 API 请求自动带上 `Authorization: Bearer <token>` header。

### 2. 主题上下文共享

```
Host App                        Superset Remote
────────                        ───────────────
主题切换按钮
(dark ↔ light)
    ↓
setThemeMode('dark')
    ↓
<MfeContextProvider
  initialContext={{
    themeMode: 'dark'         ───→  useMfeContext().context.themeMode
  }}                                  ↓
>                                    buildMergedTheme('dark', overrides)
>                                      = merge(supersetTheme,
>                                              darkThemeOverrides,
>                                              hostThemeOverrides)
>                                    ↓
>                                    <ThemeProvider theme={mergedTheme}>
>                                      <DashboardPage />
>                                    </ThemeProvider>
>                                    ↓
>                                    <Global styles={darkModeGlobalStyles} />
>                                    (覆盖硬编码的白色背景)
```

**关键**：Superset 4.1 不原生支持 dark mode（`ThemeType` 枚举仅有 `LIGHT`）。本方案通过：
1. `darkThemeOverrides` — 反转 `supersetTheme` 的所有颜色（grayscale、primary、secondary、error、warning、success、info）
2. `darkModeGlobalStyles` — Emotion `<Global>` CSS 覆盖 Superset 内部硬编码的白色背景
3. `ThemeProvider` — 在 `RootContextProviders` 内部包裹合并后的主题

### 3. 过滤器上下文共享

```
Host App                        Superset Remote
────────                        ───────────────
过滤器输入控件
(key=value)
    ↓
setFilters({ country: 'USA' })
    ↓
<MfeContextProvider
  initialContext={{
    defaultFilters: {country:'USA'}  ───→  useMfeContext().context.defaultFilters
  }}                                        ↓
>                                          window.dispatchEvent(
>                                            new CustomEvent('mfe:filterUpdate',
>                                              { detail: defaultFilters })
>                                          )
>                                          ↓
>                                          Dashboard 内部组件监听
>                                          mfe:filterUpdate 事件
>                                          → 应用过滤器到图表
```

---

## 关键配置说明

### Module Federation 共享配置

| 配置项                    | Superset (remote)             | Host App (consumer)            |
| ------------------------- | ----------------------------- | ------------------------------ |
| `name`                    | `'superset'`                  | `'host'`                       |
| `filename`                | `'remoteEntry.js'`            | -                              |
| `exposes`                 | `./Dashboard`, `./MfeContext` | -                              |
| `remotes`                 | -                             | `superset@http://...:9000/...` |
| `shared.react`            | `singleton: true`             | `singleton: true`              |
| `shared.react-dom`        | `singleton: true`             | `singleton: true`              |
| `shared.@emotion/react`   | `singleton: true`             | `singleton: true`              |
| `shared.react-router-dom` | `singleton: true`             | `singleton: true`              |

### CORS（API 跨域访问）

```python
ENABLE_CORS = True
CORS_OPTIONS = {
    'origins': ['http://localhost:3000', 'http://localhost:9000', ...],
    'supports_credentials': True,
    'allow_headers': ['*'],
}
```

### FEATURE_FLAGS

```python
FEATURE_FLAGS = { 'EMBEDDED_SUPERSET': True }
```

### publicPath（远程 chunk 加载）

```javascript
publicPath: isDevMode
  ? `http://localhost:${devserverPort}/static/assets/`
  : `${ASSET_BASE_URL}/static/assets/`,
```

### 异步入口（bootstrap 模式）

Module Federation 要求 host app 入口文件使用动态 import：

```typescript
// index.tsx - 入口
import('./bootstrap');
```

---

## Admin 登录问题

### 问题：admin 登录失败

**两种登录方式：**

| 方式         | URL                           | 需要 CSRF | 用于            |
| ------------ | ----------------------------- | --------- | --------------- |
| API 登录     | `POST /api/v1/security/login` | 否        | MFE Host App    |
| Web 表单登录 | `POST /login/`                | 是        | Superset Web UI |

**Web 表单登录** (`/login/`) 需要 CSRF token：
1. GET `/login/` 获取 HTML，从中提取 `<input name="csrf_token" value="...">`
2. POST `/login/` 时带上 `csrf_token` 字段

**API 登录** (`/api/v1/security/login`) 不需要 CSRF token，直接 POST JSON：
```json
{
  "username": "admin",
  "password": "admin",
  "provider": "db",
  "refresh": true
}
```
返回 `{ "access_token": "...", "refresh_token": "..." }`。

本方案的 Host App 使用 API 登录，因此不受 CSRF 问题影响。

如果需要修复 Superset Web UI 登录（`/login/`），确保：
1. `superset init` 已运行（同步角色权限）
2. admin 用户已创建（`flask fab create-admin`）
3. 如果仍失败，检查 Flask session 配置

---

## 遇到的问题与解决方案

| 问题                                           | 原因                               | 解决方案                                                               |
| ---------------------------------------------- | ---------------------------------- | ---------------------------------------------------------------------- |
| `superset.exe` 无法启动                        | 硬编码了错误的 Python 路径         | 直接使用 `python.exe -m flask`                                         |
| `Can't resolve '@superset-ui/core'` (652 错误) | npm workspace 符号链接指向旧路径   | 批量重建 27 个 `@superset-ui/*` 符号链接                               |
| `load_examples` 网络超时                       | CDN 无法访问                       | 下载到本地，设置 `SUPERSET_EXAMPLES_BASE_URL`                          |
| API 返回 403 Forbidden                         | 角色权限未同步                     | 运行 `security_manager.sync_role_definitions()`                        |
| `--env supersetPort=8188` 不生效               | yargs 解析格式问题                 | 使用 `--env=--supersetPort=8188`（双横线）                             |
| Talisman 配置不生效                            | debug 模式用 `TALISMAN_DEV_CONFIG` | 同时覆盖 `TALISMAN_CONFIG` 和 `TALISMAN_DEV_CONFIG`                    |
| Superset 4.1 无 dark mode                      | `ThemeType` 仅有 `LIGHT`           | 创建 `darkThemeOverrides` + `darkModeGlobalStyles`                     |
| iframe 无法实现上下文共享                      | iframe 隔离了 JS 上下文            | 改用原生 React 组件集成 (Module Federation)                            |
| Host 和 Remote Context 不同步                  | 各自创建独立 Context 实例          | 通过 Module Federation 暴露 `./MfeContext`，共享同一个 Context         |
| `RootContextProviders` 主题覆盖失效            | 使用 preamble.ts 的默认主题        | 在 RootContextProviders 内部包裹 `<ThemeProvider theme={mergedTheme}>` |

---

## 验证清单

- [x] Docker PostgreSQL (port 15435) 运行中
- [x] Docker Redis (port 16382) 运行中
- [x] 后端 (port 8188) 健康检查 HTTP 200
- [x] 前端 dev server (port 9000) 编译成功
- [x] `remoteEntry.js` 可访问 (HTTP 200, 634KB)
- [x] `remoteEntry.js` 包含 `MfeContext` 暴露
- [x] `remoteEntry.js` 包含 `@emotion/react` 和 `react-router-dom` 共享
- [x] `FEATURE_FLAGS` 包含 `EMBEDDED_SUPERSET`
- [x] API 登录 (`POST /api/v1/security/login`) 返回 access_token
- [x] Host app (port 3000) 可访问 HTTP 200
- [x] Host app 编译成功，正确连接到 remote
- [x] Host app 加载 `superset/MfeContext` 和 `superset/Dashboard` 模块
- [x] 浏览器无控制台错误

---

## 文件清单

```
superset-4.1-token/
├── superset_config.py              # Superset 配置（PG + Redis + CORS + FEATURE_FLAGS）
├── start_backend.bat               # 后端启动脚本
├── start_frontend.bat             # 前端启动脚本
├── examples-data/                  # 本地示例数据
├── superset-frontend/
│   ├── webpack.config.js           # Module Federation 配置（remote）
│   └── src/mfe/
│       ├── types.ts                # MFE 共享类型定义
│       ├── MfeContext.tsx          # 共享 React Context（通过 MF 共享）
│       ├── darkTheme.ts            # 暗色主题覆盖 + 全局 CSS
│       └── Dashboard.tsx           # 暴露的 MFE 组件（原生 React,非 iframe）
├── mfe-host/                       # Host App（consumer）
│   ├── package.json                # 依赖：react, @emotion/react, react-router-dom
│   ├── webpack.config.js           # Module Federation 配置（host）
│   ├── tsconfig.json
│   ├── public/
│   │   └── index.html
│   └── src/
│       ├── index.tsx               # 异步入口
│       ├── bootstrap.tsx           # 主应用（登录 + 主题 + 过滤器 UI）
│       └── mfe-types.d.ts          # TypeScript 声明（superset/Dashboard, superset/MfeContext）
└── MFE_IMPLEMENTATION.md           # 本文档
```

---

## 总结

通过 Module Federation 实现了 Apache Superset 4.1 Dashboard 的**原生组件集成**（非 iframe），支持三种上下文共享：

1. **认证上下文共享** — Host app 登录获取 JWT token，通过 MfeContext 传给 Superset 组件，Superset 组件用它配置 SupersetClient 单例，所有 API 请求自动带认证 header

2. **主题上下文共享** — Host app 的 dark/light 切换通过 MfeContext 联动到 Superset。由于 Superset 4.1 不原生支持 dark mode，创建了 darkThemeOverrides（颜色反转）+ darkModeGlobalStyles（CSS 覆盖），通过 ThemeProvider 注入合并后的主题

3. **过滤器上下文共享** — Host app 的过滤器控件通过 MfeContext + CustomEvent 联动到 Dashboard

**关键设计**：
- 通过 Module Federation 暴露 `./MfeContext`，确保 host 和 remote 使用**同一个 React Context 实例**
- 共享 `@emotion/react` 和 `react-router-dom` 作为 singleton，确保主题和路由一致
- 使用 `RootContextProviders` 提供 Superset 所需的完整 Provider 链（Redux、Theme、Router 等）
- 在 `RootContextProviders` 内部包裹 `<ThemeProvider>` 以覆盖默认主题
- 注入最小化 bootstrap data 供 Superset 内部模块使用
