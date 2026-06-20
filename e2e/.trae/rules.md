# E2E 子项目规则

> 完整规则见 [../../.trae/rules/project_rules.md](../../.trae/rules/project_rules.md)。本文件是 e2e 目录的精简版。

## 铁律

1. **所有 UI 操作走 `pa.*`**：`from utils import page_actions as pa`
   - 禁止直接 `page.click/fill/goto/hover/select_option/check/uncheck/press/focus`
2. **所有测试用 BDD 风格**：`@scenario(title, tags)` + 英文 `Scenario:` docstring
3. **修改 spec + COVERAGE**：测试改动同步 `spec/<module>.feature` 和 `COVERAGE.md`
4. **跨版本**：4.1 / 6.0 都跑通或 skip
5. **禁止裸 `assert`**：用 `with then(...)` 包裹

## 例外（不需要 `pa.*`）

- `page.locator(...).count()` / `text_content()` — 只读
- `page.wait_for_load_state / wait_for_timeout` — 等待
- `page.evaluate` — JS
- `page.context.request.get/post` — API
- `page.screenshot` — 截图（用 `utils.bdd._attach_screenshot`）
