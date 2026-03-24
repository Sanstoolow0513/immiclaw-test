# LLM Prompt 与异常反馈协议 v1

本文定义 `immiclaw-test` 在执行前的 Prompt 基本原则与 `screenshot + points` 失败反馈协议。

## 1) Prompt 基本原则

1. **单步执行**：每轮只做一个可验证动作，不进行跨页面的大批量操作。
2. **观察优先**：只能基于当前页面状态决策，不得假设不存在的元素。
3. **失败可追溯**：若最终判定失败，必须返回可复现的问题点描述（`points`）。
4. **证据绑定**：失败必须声明需要截图（`screenshot_required=true`），由执行端统一落地截图文件。
5. **终态明确**：当且仅当断言被验证完毕或明确失败时，输出 `final_*`。
6. **兼容旧路径**：允许旧式 `report_result(...)`，但推荐使用结构化 `status/final/evidence`。

## 2) JSON 协议

```json
{
  "thinking": "string",
  "code": "string, only optional when status is final_*",
  "status": "continue | final_pass | final_fail",
  "evidence": {
    "screenshot_required": false,
    "points": []
  },
  "final": {
    "passed": true,
    "reason": "string"
  }
}
```

### 字段约束

- `status=continue`
  - `code` 必填。
  - `final` 可为空。
- `status=final_pass`
  - `final.passed` 必须为 `true`。
  - `final.reason` 必填。
- `status=final_fail`
  - `final.passed` 必须为 `false`。
  - `final.reason` 必填。
  - `evidence.screenshot_required` 必须为 `true`。
  - `evidence.points` 至少 1 条。

### `points` 写法规范（问题点描述）

每条应包含三个信息：

- 页面区域或元素线索（如按钮文本、表单区域、URL 路径）
- 观察到的异常现象
- 预期行为

推荐模板：

`<区域/元素线索> | 现象: <异常> | 预期: <正确行为>`

## 3) 最小合法示例

### continue

```json
{
  "thinking": "先验证登录表单是否可见。",
  "code": "await page.get_by_placeholder('Email').fill(test_data['credentials']['email'])",
  "status": "continue",
  "evidence": {
    "screenshot_required": false,
    "points": []
  },
  "final": null
}
```

### final_pass

```json
{
  "thinking": "所有断言已满足。",
  "code": "",
  "status": "final_pass",
  "evidence": {
    "screenshot_required": false,
    "points": []
  },
  "final": {
    "passed": true,
    "reason": "登录成功并跳转至 /cases，页面列表可见。"
  }
}
```

### final_fail

```json
{
  "thinking": "错误提示稳定复现，断言无法满足。",
  "code": "",
  "status": "final_fail",
  "evidence": {
    "screenshot_required": true,
    "points": [
      "登录表单提交区域 | 现象: 点击登录后无跳转且页面出现 Invalid credentials | 预期: 正确凭据应跳转到 /cases",
      "URL 观察 | 现象: 30 秒后仍停留 /login | 预期: 成功登录后 URL 应变化"
    ]
  },
  "final": {
    "passed": false,
    "reason": "登录主断言失败，已稳定复现。"
  }
}
```

## 4) 验收清单

- 出现 `final_fail` 时，执行端必须拿到：
  - 非空 `evidence.points`
  - `evidence.screenshot_required=true`
- `points` 文案可读、可定位、可复现。
- 旧响应格式（仅 `thinking/code`）不应导致流程中断。
