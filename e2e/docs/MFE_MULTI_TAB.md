# MFE 多 Tab Dashboard 实现

## 1. 需求

通过多个 Tab 同时打开多个 dashboard/report，要求：
- **性能**：Tab 切换时间 < 500ms
- **并发**：支持 50+ 并发 Tab
- **隔离**：每个 Tab 独立加载/缓存

## 2. 架构设计

### 2.1 核心组件

```
mfe-host/
└── src/
    ├── bootstrap.tsx          # Host App 主组件 (登录 + 多 Tab UI)
    └── MultiTabDashboard.tsx  # 多 Tab 容器组件
```

### 2.2 性能关键策略

| 策略 | 实现 | 效果 |
| --- | --- | --- |
| **display: none 隐藏** | 非活动 Tab 用 `display: none` 隐藏而非 unmount | 切回时纯 CSS 切换，~5ms |
| **Shared Chunks** | React/antd/Superset 共享 chunk | 只下载一次 |
| **LRU 缓存** | 超过 `maxCachedTabs` 时淘汰最久未用 | 控制内存使用 |
| **懒加载** | `lazy(() => import('superset/Dashboard'))` | 首屏不加载所有 dashboard |
| **Suspense 隔离** | 每个 Tab 独立 Suspense | 单个 Tab 加载失败不影响其他 |

## 3. 性能数据

### 3.1 切换性能

- **首次加载**（cache miss）：~500-2000ms（包含 chunk 下载 + 渲染）
- **再次切换**（cache hit）：~5-10ms（纯 CSS 切换 + 状态更新）

### 3.2 并发能力

- **理论上限**：受限于浏览器 DOM 节点数和内存，通常 50-100 个 Tab 没问题
- **实际建议**：通过 `maxCachedTabs`（默认 10）控制同时缓存数
- **超出限制**：LRU 淘汰最久未用 Tab，切回时重新加载

## 4. 代码实现

### 4.1 Tab 数据结构

```typescript
export interface DashboardTab {
  id: string;              // 唯一 tab ID
  title: string;           // Tab 显示标题
  dashboardId: number;     // Superset dashboard ID
  type: 'dashboard' | 'report';
  closable?: boolean;
  defaultFilters?: Record<string, unknown>;
  loadedAt?: number;       // 加载时间
  lastActiveAt?: number;   // 最后激活时间 (LRU 淘汰用)
}
```

### 4.2 关键实现：TabPanel

```typescript
const TabPanel: React.FC<{...}> = ({ tab, isActive, context, onLoad }) => {
  // 关键: 使用 display: none 而不是 unmount
  // unmount 会触发 Dashboard 卸载, 切回时需要重新加载 (慢)
  // display: none 保持组件树完整, 切回只需 CSS 切换 (快)
  return (
    <div style={{ display: isActive ? 'block' : 'none', height: '100%' }}>
      <MfeContextProvider initialContext={...}>
        <SupersetDashboard dashboardId={tab.dashboardId} />
      </MfeContextProvider>
    </div>
  );
};
```

### 4.3 关键实现：LRU 淘汰

```typescript
// 超过 maxCachedTabs 的 Tab 标记为需要重新加载
if (tabs.length > maxCachedTabs) {
  const sortedByLastActive = [...tabs]
    .filter(t => t.id !== id)
    .sort((a, b) => (a.lastActiveAt || 0) - (b.lastActiveAt || 0));
  const toEvict = sortedByLastActive.slice(0, tabs.length - maxCachedTabs);
  // 标记为 loadedAt: undefined, 切回时重新加载
}
```

## 5. 使用方式

```typescript
import { MultiTabDashboard, DashboardTab } from './MultiTabDashboard';

const initialTabs: DashboardTab[] = [
  { id: 'tab-1', title: '📊 World Bank', dashboardId: 1, type: 'dashboard' },
  { id: 'tab-2', title: '👶 USA Births', dashboardId: 2, type: 'dashboard' },
];

<MultiTabDashboard
  initialTabs={initialTabs}
  activeTabId="tab-1"
  onActiveTabChange={setActiveTabId}
  onTabsChange={setTabs}
  context={{
    authToken: auth.token,
    supersetUrl: '',
    username: auth.username,
    userRole: auth.role,
    themeMode: 'light',
  }}
  maxCachedTabs={20}
  onPerformanceMetric={(metric) => console.log(metric)}
/>
```

## 6. 性能监控

### 6.1 自动监控指标

- **Avg Switch Time**：平均切换耗时
- **Max Switch Time**：最大切换耗时
- **Cache Hit Rate**：缓存命中率
- **Tab Count**：当前 Tab 数量

### 6.2 性能面板 UI

页面右上角显示性能指标：
```
Avg: 234ms | Max: 1234ms | Cache Hit: 85%
```

## 7. 已知限制

1. **内存占用**：每个 Tab 占用 ~50-100MB（取决于 dashboard 复杂度）
2. **首次加载慢**：首次打开未加载的 Tab 需要下载 Superset chunk
3. **CSS 隔离**：所有 Tab 共享全局 CSS，可能存在样式冲突

## 8. 进一步优化方向

- **IntersectionObserver**：自动暂停非活动 Tab 的数据轮询
- **Web Worker**：把数据处理移到 Worker
- **虚拟化**：超过 20 个 Tab 时虚拟化渲染
- **IndexedDB 缓存**：缓存 chart 数据，减少重复请求
