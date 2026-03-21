# ImmiClaw Web 测试场景设计

## 概述

为 `immiclaw-test` 构建基于 LLM + Playwright 的 Web 测试场景集，从终端用户视角全面测试 ImmiClaw EB-1A 移民申请助手的前端功能。测试覆盖页面可用性、交互响应、数据一致性，以及 AI 聊天的业务流程。

## 核心决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 认证策略 | 每个场景从登录开始 | 最贴近真实用户体验 |
| 凭据管理 | `test_data` 灵活配置 + 注册场景 | 适配多种环境（本地、部署、全新） |
| 场景组织 | 前缀命名扁平结构 | 零改动适配现有框架，天然分组 |
| 覆盖策略 | 两层：冒烟测试 + 用户旅程 | 细粒度定位 + 端到端验证 |
| 检测范围 | 页面级 + 交互级 + 数据一致性 | 全面捕获用户可感知的问题 |
| 聊天测试深度 | 到业务流程级 | 初始评估、选项卡、文件上下文 |

## 场景清单

### 前缀规范

- `smoke-` — 细粒度功能点冒烟测试，单一模块，快速定位
- `journey-` — 跨模块用户旅程集成测试，模拟真实使用流程

### 场景文件结构

```
config/scenarios/
├── example.yaml               # 保留现有示例
├── smoke-login.yaml           # 认证：正常登录
├── smoke-login-error.yaml     # 认证：登录失败与恢复
├── smoke-register.yaml        # 认证：新用户注册
├── smoke-case-list.yaml       # 案件：列表页展示
├── smoke-case-create.yaml     # 案件：新建（问卷+简历）
├── smoke-case-manage.yaml     # 案件：重命名与删除
├── smoke-chat-basic.yaml      # 聊天：基础收发消息
├── smoke-chat-assessment.yaml # 聊天：初始评估流程
├── smoke-chat-interaction.yaml# 聊天：停止生成/历史/附件
├── smoke-file-upload.yaml     # 文件：上传与预览
├── smoke-file-browse.yaml     # 文件：浏览与管理操作
├── smoke-settings.yaml        # 设置：主题/密码/登出
├── journey-new-user.yaml      # 旅程：新用户完整体验
├── journey-case-workflow.yaml # 旅程：日常案件工作流
└── journey-file-management.yaml # 旅程：材料整理流程
```

---

## 冒烟测试场景详细设计

### 1. `smoke-login.yaml` — 正常登录

- **name**: `smoke-login`
- **description**: 验证使用正确凭据登录后成功跳转到案件列表页
- **target_url**: `{base_url}/login`
- **goal**: 打开登录页面，使用 test_data 中的凭据登录，验证成功跳转到案件列表页
- **assertions**:
  - 登录页正常加载，显示邮箱和密码输入框
  - 输入凭据后点击登录按钮无报错
  - 成功跳转到 /cases 页面
  - 案件列表页正常展示内容
- **max_steps**: 15
- **timeout_seconds**: 60
- **test_data**: `credentials: {email: "test@example.com", password: "TestPass123!"}`

### 2. `smoke-login-error.yaml` — 登录失败与恢复

- **name**: `smoke-login-error`
- **description**: 验证错误凭据登录时显示错误提示，且能用正确凭据恢复登录
- **target_url**: `{base_url}/login`
- **goal**: 先用错误密码尝试登录，确认显示错误提示且不跳转；再用正确凭据登录成功
- **assertions**:
  - 输入错误凭据后显示错误提示信息
  - 页面仍停留在登录页，未跳转
  - 输入正确凭据后成功登录并跳转到 /cases
- **max_steps**: 20
- **timeout_seconds**: 60
- **test_data**:
  - `wrong_credentials: {email: "test@example.com", password: "WrongPass!"}`
  - `correct_credentials: {email: "test@example.com", password: "TestPass123!"}`

### 3. `smoke-register.yaml` — 新用户注册

- **name**: `smoke-register`
- **description**: 验证新用户注册流程完整可用
- **target_url**: `{base_url}/register`
- **goal**: 打开注册页面，填写注册信息并提交，验证注册成功
- **assertions**:
  - 注册页面正常加载，显示注册表单
  - 填写信息并提交后无错误
  - 注册成功后跳转到案件列表或登录页
- **max_steps**: 15
- **timeout_seconds**: 60
- **test_data**: `new_user: {email: "newuser-{timestamp}@test.com", password: "NewUserPass123!", name: "测试用户"}`

### 4. `smoke-case-list.yaml` — 案件列表页

- **name**: `smoke-case-list`
- **description**: 验证登录后案件列表页正常展示
- **target_url**: `{base_url}/login`
- **goal**: 登录后验证案件列表页正常加载，检查页面元素完整性
- **assertions**:
  - 登录成功并跳转到 /cases
  - 页面正常加载无白屏
  - 如有案件则显示案件卡片（含标题、阶段信息）
  - 新建案件按钮可见可点击
  - 页面无 JS 错误或异常提示
- **max_steps**: 20
- **timeout_seconds**: 60
- **test_data**: `credentials: {email: "test@example.com", password: "TestPass123!"}`

### 5. `smoke-case-create.yaml` — 新建案件

- **name**: `smoke-case-create`
- **description**: 验证新建案件完整流程——填写问卷、上传简历、提交
- **target_url**: `{base_url}/login`
- **goal**: 登录后点击新建案件，填写问卷信息并上传简历，提交后验证案件创建成功
- **assertions**:
  - 点击新建案件后问卷页正常加载
  - 填写基础信息（姓名、出生日期、工作单位等）无异常
  - 上传简历文件成功
  - 提交后跳转到欢迎页或主工作区
  - 回到案件列表可看到刚创建的案件
- **max_steps**: 35
- **timeout_seconds**: 120
- **test_data**:
  - `credentials: {email: "test@example.com", password: "TestPass123!"}`
  - `questionnaire: {name: "张三", birth_date: "1990-01-15", employer: "某科技公司", position: "高级研究员", industry: "人工智能", education: "博士", major: "计算机科学", immigration_intent: "希望通过EB-1A获得美国绿卡"}`
  - `resume_file: "assets/files/test-resume.pdf"`

### 6. `smoke-case-manage.yaml` — 案件管理

- **name**: `smoke-case-manage`
- **description**: 验证案件的重命名和删除操作
- **target_url**: `{base_url}/login`
- **goal**: 登录后在案件列表中对已有案件执行重命名和删除操作，验证操作结果正确
- **assertions**:
  - 案件列表中至少有一个案件
  - 重命名案件后新名称正确显示
  - 删除案件后该案件从列表消失
  - 操作过程中无错误提示
- **max_steps**: 25
- **timeout_seconds**: 90
- **test_data**:
  - `credentials: {email: "test@example.com", password: "TestPass123!"}`
  - `rename_to: "测试重命名案件"`

### 7. `smoke-chat-basic.yaml` — 基础聊天

- **name**: `smoke-chat-basic`
- **description**: 验证主工作区聊天的基本收发消息功能
- **target_url**: `{base_url}/login`
- **goal**: 登录后进入案件工作区，发送一条消息，验证 AI 正常回复
- **assertions**:
  - 主工作区正常加载，聊天区域可见
  - 输入框可用，能输入文字
  - 发送消息后出现正在生成状态
  - 一定时间内收到 AI 回复
  - 回复内容非空且可读
  - 无网络错误或超时提示
- **max_steps**: 25
- **timeout_seconds**: 120
- **test_data**:
  - `credentials: {email: "test@example.com", password: "TestPass123!"}`
  - `case_id: "existing-case-id"`
  - `message: "你好，请简单介绍一下EB-1A申请流程"`

### 8. `smoke-chat-assessment.yaml` — 初始评估

- **name**: `smoke-chat-assessment`
- **description**: 验证初始评估流程能正常触发并完成
- **target_url**: `{base_url}/login`
- **goal**: 登录后进入已提交问卷的案件工作区，验证初始评估自动触发并产生有意义的回复
- **assertions**:
  - 进入工作区后初始评估触发
  - 正在生成状态出现
  - 收到有意义的评估回复（非空、与 EB-1A 相关）
  - 如出现选项卡（ChoicesCard），点击选项后能正常响应
  - 聊天无中断或错误
- **max_steps**: 30
- **timeout_seconds**: 180
- **test_data**:
  - `credentials: {email: "test@example.com", password: "TestPass123!"}`
  - `case_id: "case-with-questionnaire"`

### 9. `smoke-chat-interaction.yaml` — 聊天高级交互

- **name**: `smoke-chat-interaction`
- **description**: 验证停止生成、消息历史加载、带附件发消息等高级功能
- **target_url**: `{base_url}/login`
- **goal**: 登录后进入案件工作区，测试停止生成、刷新后历史保留、带附件发消息并验证 AI 回复
- **assertions**:
  - 发送消息后在生成过程中点击停止，生成确实停止
  - 页面刷新后消息历史正确加载
  - 上传文件后发送带附件的消息
  - AI 回复体现了对文件内容的理解
  - 滚动加载更多历史消息无异常
- **max_steps**: 35
- **timeout_seconds**: 180
- **test_data**:
  - `credentials: {email: "test@example.com", password: "TestPass123!"}`
  - `case_id: "case-with-history"`
  - `attachment_file: "assets/files/test-doc.pdf"`
  - `message_with_file: "请帮我分析这份文件的内容"`

### 10. `smoke-file-upload.yaml` — 文件上传

- **name**: `smoke-file-upload`
- **description**: 验证文件上传和预览功能
- **target_url**: `{base_url}/login`
- **goal**: 登录后进入案件工作区，上传文件并验证文件可见可预览
- **assertions**:
  - 文件浏览区正常加载
  - 点击上传按钮弹出上传对话框
  - 上传测试文件成功，无错误
  - 文件出现在文件列表中
  - 点击文件能正常预览
  - 文件名正确显示
- **max_steps**: 25
- **timeout_seconds**: 90
- **test_data**:
  - `credentials: {email: "test@example.com", password: "TestPass123!"}`
  - `case_id: "existing-case-id"`
  - `upload_file: "assets/files/test-upload.pdf"`

### 11. `smoke-file-browse.yaml` — 文件浏览与管理

- **name**: `smoke-file-browse`
- **description**: 验证文件浏览、文件夹操作、文件重命名和删除
- **target_url**: `{base_url}/login`
- **goal**: 登录后在案件工作区验证目录树展示、新建文件夹、重命名、删除等文件管理操作
- **assertions**:
  - 文件目录树正常展示
  - 创建新文件夹成功且出现在目录中
  - 文件夹可重命名
  - 文件可重命名且名称更新正确
  - 文件和文件夹可删除
  - 右键菜单正常弹出可操作
  - 操作过程中无错误提示
- **max_steps**: 30
- **timeout_seconds**: 90
- **test_data**:
  - `credentials: {email: "test@example.com", password: "TestPass123!"}`
  - `case_id: "case-with-files"`
  - `new_folder_name: "测试文件夹"`
  - `rename_folder_to: "重命名文件夹"`
  - `rename_file_to: "重命名文件.pdf"`

### 12. `smoke-settings.yaml` — 设置页面

- **name**: `smoke-settings`
- **description**: 验证主题切换、密码修改和退出登录功能
- **target_url**: `{base_url}/login`
- **goal**: 登录后进入设置页面，测试主题切换、密码修改和退出登录
- **assertions**:
  - 设置页面正常加载
  - 主题选项可见，切换到深色主题后样式变化
  - 切换回浅色主题恢复正常
  - 密码修改表单可用，提交后有成功反馈
  - 退出登录后跳转回登录页
  - 用新密码可重新登录
- **max_steps**: 25
- **timeout_seconds**: 90
- **test_data**:
  - `credentials: {email: "test@example.com", password: "TestPass123!"}`
  - `new_password: "NewTestPass123!"`

---

## 用户旅程场景详细设计

### 13. `journey-new-user.yaml` — 新用户完整体验

- **name**: `journey-new-user`
- **description**: 模拟全新用户从注册到首次使用的完整旅程
- **target_url**: `{base_url}/register`
- **goal**: 注册新账号，创建第一个案件并完成问卷，经过欢迎页进入工作区，确认初始评估触发
- **assertions**:
  - 注册成功并自动登录
  - 案件列表初始为空
  - 新建案件并完成问卷提交
  - 简历上传成功
  - 欢迎页正常展示
  - 自动跳转到主工作区
  - 初始评估触发并收到 AI 回复
  - Todo 进度面板可见且显示阶段信息
  - 全程无白屏、无 JS 错误、无无响应状态
- **max_steps**: 50
- **timeout_seconds**: 300
- **test_data**:
  - `new_user: {email: "journey-{timestamp}@test.com", password: "JourneyPass123!", name: "旅程测试用户"}`
  - `questionnaire: {name: "李四", birth_date: "1988-06-20", employer: "某研究院", position: "首席研究员", industry: "生物技术", education: "博士", major: "分子生物学", immigration_intent: "希望以杰出人才身份移民美国"}`
  - `resume_file: "assets/files/test-resume.pdf"`

### 14. `journey-case-workflow.yaml` — 日常案件工作流

- **name**: `journey-case-workflow`
- **description**: 模拟已有用户的日常工作流——对话、上传文件、带上下文对话、查看进度
- **target_url**: `{base_url}/login`
- **goal**: 登录后打开案件，与 AI 对话，上传文件后带附件继续对话，查看 Todo 进度
- **assertions**:
  - 登录后案件列表加载正常
  - 点击案件进入工作区
  - 发送消息并收到 AI 回复
  - 上传文件到指定目录成功
  - 带附件发送消息后 AI 回复体现文件理解
  - Todo 进度面板可点击跳转
  - 刷新后聊天历史完整保留
  - 全程无超时或无响应
- **max_steps**: 45
- **timeout_seconds**: 240
- **test_data**:
  - `credentials: {email: "test@example.com", password: "TestPass123!"}`
  - `case_id: "existing-case-id"`
  - `message: "请帮我分析一下我的材料准备情况"`
  - `upload_file: "assets/files/test-doc.pdf"`
  - `message_with_file: "请查看我上传的这份推荐信，帮我评估一下"`

### 15. `journey-file-management.yaml` — 材料整理流程

- **name**: `journey-file-management`
- **description**: 模拟用户集中整理案件材料的完整流程
- **target_url**: `{base_url}/login`
- **goal**: 登录后进入案件，创建文件夹结构，上传文件，在文件夹间组织，预览、重命名、删除
- **assertions**:
  - 创建多个文件夹成功
  - 上传文件到指定文件夹
  - 文件列表正确反映文件位置
  - 文件预览正常（PDF 能渲染）
  - 重命名文件/文件夹后名称更新
  - 删除操作后项目消失
  - 文件变更通知正常出现
  - 全程操作流畅无卡顿或错误
- **max_steps**: 40
- **timeout_seconds**: 180
- **test_data**:
  - `credentials: {email: "test@example.com", password: "TestPass123!"}`
  - `case_id: "existing-case-id"`
  - `folders: ["推荐信", "获奖材料", "媒体报道"]`
  - `upload_files: ["assets/files/rec-letter.pdf", "assets/files/award.pdf"]`

---

## 通用检测要求

所有场景的 goal 描述中应隐含以下检测：

1. **页面级**：无白屏、无 404/500、无 JS 控制台错误、页面标题非空
2. **交互级**：按钮点击有响应、表单提交有反馈、加载状态正确显示和消失
3. **数据一致性**：创建的数据出现在列表中、删除的数据从列表消失、修改的数据更新正确
4. **网络健壮性**：API 调用有响应、SSE 流正常工作、超时时有用户可理解的提示

## 测试数据资产

需要在 `assets/files/` 目录下准备以下测试文件：

- `test-resume.pdf` — 测试用简历
- `test-upload.pdf` — 通用上传测试文件
- `test-doc.pdf` — 带附件聊天测试文件
- `rec-letter.pdf` — 模拟推荐信
- `award.pdf` — 模拟获奖证明

## 运行方式

```bash
# 运行单个冒烟测试
python main.py config/scenarios/smoke-login.yaml

# 运行单个旅程测试
python main.py config/scenarios/journey-new-user.yaml

# 按前缀批量运行（需脚本支持）
for f in config/scenarios/smoke-*.yaml; do python main.py "$f"; done
for f in config/scenarios/journey-*.yaml; do python main.py "$f"; done
```
