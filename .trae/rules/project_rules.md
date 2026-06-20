# Project Rules for Superset E2E Tests

> 任何 Agent 维护本仓库的 E2E 测试时必须遵守的硬性规则。
> 修改本文件前需获得用户同意。

---

## 1. 所有 UI 操作必须走 `utils.page_actions`

### 1.1 强制要求

任何与浏览器页面的交互 **必须** 通过 `utils.page_actions`（别名 `pa`）执行，**禁止** 直接调用 `page.goto/click/fill/hover/select_option/check/uncheck/press/focus` 等。

```python
# ✅ 正确
from utils import page_actions as pa
pa.goto(page, url)
pa.click(page, "button.submit")
pa.fill(page, 'input[name="q"]', "hello")
pa.hover(page, ".menu-item")
pa.select(page, "select#x", "v")
pa.press(page, "Enter")

# ❌ 错误（会被拒绝）
page.goto(url)
page.click("button.submit")
page.fill('input[name="q"]', "hello")
```

### 1.2 例外（不必走 `pa.*`）

| 例外 | 原因 |
| --- | --- |
| `page.locator(...).count()` | 只读查询，不触发用户动作 |
| `page.locator(...).first.text_content()` | 只读 |
| `page.wait_for_load_state(...)` | 等待而非动作 |
| `page.wait_for_timeout(...)` | 等待 |
| `page.evaluate(...)` | JS 注入 |
| `page.context.request.get/post(...)` | API 客户端调用 |
| `page.screenshot(...)` | 截图（用 `_attach_screenshot`） |
| `page.keyboard.press(...)` 配合 `pa.press` | 高亮 + press 二选一，`pa.press` 优先 |

### 1.3 理由

- `pa.*` 在 headed 模式下自动给目标元素加红框 + 角标 + 呼吸动画，便于肉眼观察测试在做什么
- `pa.*` 自动注册为 Allure step（`Action: click -> <selector>`）
- `pa.*` 保留高亮 300ms 后再继续，避免 headed 模式下闪烁

---

## 2. 所有 UI 测试用 BDD 风格

### 2.1 测试函数必须有 `@scenario(...)` 装饰器

```python
@scenario("Title", tags=("module",))
def test_xxx(page):
    """Scenario: English title
    Given ...
    When ...
    Then ...
    """
```

### 2.2 docstring 用英文 Given-When-Then

- `Scenario:` / `Given` / `When` / `And` / `Then` 关键字英文
- 与 `spec/<module>.feature` 的 Scenario 标题一一对应
- spec 文件首行 `# language: en`

### 2.3 step context manager 来自 `utils.bdd`

```python
from utils.bdd import given, when, then, and_

with when("the user clicks submit", page=page, focus="button.submit"):
    pa.click(page, "button.submit")
with then("the response is 200", screenshot=True):
    assert resp.status == 200
```

---

## 3. 选择器规范

- 4.1 / 6.0 兼容：用 `,` 并列
- 优先用 `data-test` 属性，没有则用 `name` / `id`
- 跨版本组件（4.1 jinja、6.0 ant）都要覆盖
- 选择器作为 Page Object 的类常量：`SEL_USERNAME = ...`

---

## 4. 新增/修改测试流程

1. **先写 spec**：在 `e2e/spec/<module>.feature` 加 Scenario
2. **再写实现**：`e2e/tests/<module>/test_*.py` 加 `def test_*`
3. **更新 COVERAGE**：在 `e2e/COVERAGE.md` 改对应行状态 `[ ] → [x]`
4. **跑通验证**：`python run.py -m <module> --headed` 至少一次
5. **同时跑 4.1 + 6.0**：保证 `[-v4.1]` / `[-v6.0]` 都通过或 skip

---

## 5. 禁止事项

- ❌ 禁止直接 `page.click/fill/goto/...`
- ❌ 禁止裸 `assert`，必须用 `with then(...)` 包裹或写有意义的 message
- ❌ 禁止中英文混用 docstring
- ❌ 禁止新 Page Object 不 import `from utils import page_actions as pa`
- ❌ 禁止跳过 `COVERAGE.md` 状态更新
- ❌ 禁止把临时调试脚本（debug_*.py）提交进 `tests/` 或 `pages/`
- ❌ 禁止使用裸 `time.sleep`，用 `utils.stability.wait_for` 或 `page.wait_for_timeout`

---

## 6. 文件归属

| 类型 | 路径 |
| --- | --- |
| Page Object | `e2e/pages/<page>_page.py` |
| 测试实现 | `e2e/tests/<module>/test_*.py` |
| BDD 规范 | `e2e/spec/<module>.feature` |
| 工具 | `e2e/utils/*.py` |
| Fixture | `e2e/fixtures/*.py` |
| 进度表 | `e2e/COVERAGE.md` |
