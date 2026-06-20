# tests/auth/

认证 / 登录 / 登出相关测试。

## 用例

| 测试                        | 标记              | 验证内容                                       |
| --------------------------- | ----------------- | ---------------------------------------------- |
| `test_admin_login_success`  | `auth smoke`      | admin 用正确凭据登录成功，URL 离开 `/login/`   |
| `test_wrong_password_fails` | `auth`            | 错误密码应登录失败（停留在 `/login/` 或有错误） |
| `test_logout_via_api`       | `auth`            | 通过 `GET /logout/` 登出，session 被清         |
| `test_logout`               | `auth`            | 点击 UI 菜单 Logout（找不到则 skip）           |

## 运行

```bash
python run.py -m auth
```

## 跨版本说明

- 4.1：菜单按钮在右上角，class `navbar-right`
- 6.0：菜单按钮在 antd 头像 `.ant-avatar`
- 找不到菜单时 `test_logout` 会 `pytest.skip`；推荐用 `test_logout_via_api`
