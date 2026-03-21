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

## 测试隔离策略

### 账号隔离

每个场景使用独立的测试账号以避免状态污染：

| 场景类型 | 账号策略 | 邮箱示例 |
|----------|----------|----------|
| 只读/观察类（smoke-login, smoke-case-list） | 共享只读账号 | `readonly@test.com` |
| 写入/修改类（smoke-case-create, smoke-file-*） | 按场景命名的专用账号 | `case-create@test.com`、`file-upload@test.com` |
| 破坏类（smoke-case-manage, smoke-settings） | 含 `{timestamp}` 的一次性账号 | `case-manage-{timestamp}@test.com` |
| 注册类（smoke-register, journey-new-user） | 含 `{timestamp}` 的唯一邮箱 | `newuser-{timestamp}@test.com` |

### 环境预置

运行测试前需预置以下账号（通过 seed 脚本或手动创建）：

| 账号 | 密码 | 用途 | 需预置数据 |
|------|------|------|------------|
| `readonly@test.com` | `TestPass123!` | 只读场景 | 至少 1 个已激活案件 |
| `case-create@test.com` | `TestPass123!` | 创建案件 | 无 |
| `chat-basic@test.com` | `TestPass123!` | 基础聊天 | 至少 1 个已激活案件 |
| `chat-assess@test.com` | `TestPass123!` | 初始评估 | 至少 1 个已提交问卷的案件 |
| `chat-interact@test.com` | `TestPass123!` | 聊天交互 | 至少 1 个有聊天历史的案件 |
| `file-upload@test.com` | `TestPass123!` | 文件上传 | 至少 1 个已激活案件 |
| `file-browse@test.com` | `TestPass123!` | 文件浏览 | 至少 1 个含文件的案件 |
| `journey-workflow@test.com` | `TestPass123!` | 日常工作流 | 至少 1 个已激活案件 |
| `journey-files@test.com` | `TestPass123!` | 材料整理 | 至少 1 个已激活案件 |

含 `{timestamp}` 的账号由场景运行时动态创建（通过注册 API 或注册页面），无需预置。

### case_id 解析策略

`test_data` 中的 `case_id` 支持两种模式：

1. **显式 ID**：直接填写真实 case_id（适合有 seed 数据的环境）
2. **`"auto"`（默认推荐）**：当 `case_id` 为 `"auto"` 或省略时，LLM 应从案件列表中选择第一个可用案件；若列表为空，先创建一个再进入

goal 描述中会明确指引 LLM 的行为，例如："登录后，从案件列表中选择第一个案件进入工作区"。

### 模板变量

场景 YAML 中支持以下模板变量，由运行器在加载场景时替换：

| 变量 | 说明 | 替换时机 |
|------|------|----------|
| `{base_url}` | 目标站点地址 | 加载时，取自 settings.yaml |
| `{timestamp}` | 当前时间戳（秒级） | 加载时，由运行器生成 |

### 执行顺序

冒烟测试场景设计为**可独立执行、无顺序依赖**。如需串行运行全部场景，推荐顺序：`smoke-register` → `smoke-login` → `smoke-login-error` → `smoke-case-*` → `smoke-chat-*` → `smoke-file-*` → `smoke-settings` → `journey-*`。

## test_data 字段约定

| 字段 | 类型 | 用途 | 使用场景 |
|------|------|------|----------|
| `credentials` | `{email, password}` | 登录凭据 | 需要登录的场景 |
| `wrong_credentials` | `{email, password}` | 错误凭据 | 登录失败测试 |
| `correct_credentials` | `{email, password}` | 正确凭据（配合 wrong 使用） | 登录恢复测试 |
| `new_user` | `{email, password, name}` | 注册信息 | 注册场景 |
| `case_id` | `string` | 目标案件 ID（或 `"auto"`） | 需要进入案件的场景 |
| `questionnaire` | `{name, birth_date, employer, position, industry, education, major, immigration_intent}` | 问卷数据 | 创建案件场景 |
| `resume_file` | `string` | 简历文件相对路径 | 创建案件场景 |
| `upload_file` / `upload_files` | `string` / `list[string]` | 上传文件路径 | 文件上传场景 |
| `attachment_file` | `string` | 聊天附件路径 | 带附件聊天场景 |
| `message` / `message_with_file` | `string` | 聊天消息内容 | 聊天场景 |
| `new_password` | `string` | 新密码 | 设置场景 |
| `rename_to` | `string` | 重命名目标名称 | 案件管理场景 |
| `new_folder_name` / `rename_folder_to` / `rename_file_to` | `string` | 文件夹/文件操作名称 | 文件管理场景 |
| `folders` | `list[string]` | 批量创建文件夹名称 | 旅程场景 |

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
├── smoke-chat-interaction.yaml # 聊天：停止生成/历史/附件
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
  - URL 变为 /cases
  - 页面有可见内容（非白屏），案件列表区域已渲染
- **max_steps**: 15
- **timeout_seconds**: 60
- **test_data**: `credentials: {email: "readonly@test.com", password: "TestPass123!"}`

### 2. `smoke-login-error.yaml` — 登录失败与恢复

- **name**: `smoke-login-error`
- **description**: 验证错误凭据登录时显示错误提示，且能用正确凭据恢复登录
- **target_url**: `{base_url}/login`
- **goal**: 先用错误密码尝试登录，确认显示错误提示且不跳转；再用正确凭据登录成功
- **assertions**:
  - 输入错误凭据后页面出现可见的错误提示文本
  - URL 仍为 /login，未跳转
  - 输入正确凭据后成功登录，URL 变为 /cases
- **max_steps**: 20
- **timeout_seconds**: 60
- **test_data**:
  - `wrong_credentials: {email: "readonly@test.com", password: "WrongPass!"}`
  - `correct_credentials: {email: "readonly@test.com", password: "TestPass123!"}`

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
  - 登录成功后 URL 变为 /cases
  - 页面有可见内容（非白屏）
  - 如有案件则显示案件卡片（含标题文本）
  - 新建案件按钮可见
  - 页面无可见错误提示
- **max_steps**: 20
- **timeout_seconds**: 60
- **test_data**: `credentials: {email: "readonly@test.com", password: "TestPass123!"}`

### 5. `smoke-case-create.yaml` — 新建案件

- **name**: `smoke-case-create`
- **description**: 验证新建案件完整流程——填写问卷、上传简历、提交
- **target_url**: `{base_url}/login`
- **goal**: 登录后点击新建案件，填写问卷信息并上传简历，提交后验证案件创建成功
- **assertions**:
  - 点击新建案件后 URL 包含 /cases/new，页面显示表单
  - 填写各字段后字段值正确显示（无清空或报错）
  - 上传简历文件后文件名出现在页面上
  - 提交后 URL 变化（离开 /cases/new）
  - 导航回案件列表后，新案件的名称出现在列表中
- **max_steps**: 35
- **timeout_seconds**: 120
- **test_data**:
  - `credentials: {email: "case-create@test.com", password: "TestPass123!"}`
  - `questionnaire: {name: "张三", birth_date: "1990-01-15", employer: "某科技公司", position: "高级研究员", industry: "人工智能", education: "博士", major: "计算机科学", immigration_intent: "希望通过EB-1A获得美国绿卡"}`
  - `resume_file: "assets/files/test-resume.pdf"`

### 6. `smoke-case-manage.yaml` — 案件管理

- **name**: `smoke-case-manage`
- **description**: 验证案件的重命名和删除操作
- **target_url**: `{base_url}/login`
- **goal**: 登录后，先创建一个临时案件用于测试，然后对该案件执行重命名和删除操作
- **assertions**:
  - 创建临时案件成功，该案件出现在列表中
  - 重命名案件后列表中显示新名称
  - 删除案件后该案件从列表中消失
  - 操作过程中无可见错误提示
- **max_steps**: 30
- **timeout_seconds**: 90
- **test_data**:
  - `credentials: {email: "case-manage-{timestamp}@test.com", password: "TestPass123!"}`
  - `rename_to: "测试重命名案件"`

### 7. `smoke-chat-basic.yaml` — 基础聊天

- **name**: `smoke-chat-basic`
- **description**: 验证主工作区聊天的基本收发消息功能
- **target_url**: `{base_url}/login`
- **goal**: 登录后，从案件列表中选择第一个案件进入工作区，发送一条消息，验证 AI 正常回复
- **assertions**:
  - 主工作区正常加载，聊天区域可见
  - 输入框可用，能输入文字
  - 发送消息后出现"正在生成"加载状态
  - 60 秒内收到 AI 回复（回复文本长度 > 0）
  - 回复消息渲染在聊天记录中
  - 页面无可见错误提示
- **max_steps**: 25
- **timeout_seconds**: 120
- **test_data**:
  - `credentials: {email: "chat-basic@test.com", password: "TestPass123!"}`
  - `case_id: "auto"`
  - `message: "你好，请简单介绍一下EB-1A申请流程"`

### 8. `smoke-chat-assessment.yaml` — 初始评估

- **name**: `smoke-chat-assessment`
- **description**: 验证初始评估流程能正常触发并完成
- **target_url**: `{base_url}/login`
- **goal**: 登录后进入已提交问卷的案件工作区，验证初始评估自动触发并产生回复
- **assertions**:
  - 进入工作区后出现"正在生成"加载状态（评估触发）
  - 90 秒内收到评估回复（回复文本长度 > 0）
  - 回复中包含 EB-1A 相关关键词（如"杰出人才"、"EB-1A"、"移民"之一）
  - 如出现选项卡组件，点击某个选项后聊天区域出现新内容或加载状态
  - 聊天区域无可见错误提示
- **max_steps**: 30
- **timeout_seconds**: 180
- **test_data**:
  - `credentials: {email: "chat-assess@test.com", password: "TestPass123!"}`
  - `case_id: "auto"`

### 9. `smoke-chat-interaction.yaml` — 聊天高级交互

- **name**: `smoke-chat-interaction`
- **description**: 验证停止生成、消息历史加载、带附件发消息等高级功能
- **target_url**: `{base_url}/login`
- **goal**: 登录后进入案件工作区，测试停止生成、刷新后历史保留、带附件发消息
- **assertions**:
  - 发送消息后在生成过程中点击停止按钮，加载状态消失（生成停止）
  - 页面刷新后之前的消息仍然可见（历史加载正常）
  - 上传文件后发送带附件的消息，消息成功发送
  - AI 回复文本长度 > 0 且回复中提及了上传文件的文件名
  - 页面无可见错误提示
- **max_steps**: 35
- **timeout_seconds**: 180
- **test_data**:
  - `credentials: {email: "chat-interact@test.com", password: "TestPass123!"}`
  - `case_id: "auto"`
  - `attachment_file: "assets/files/test-doc.pdf"`
  - `message_with_file: "请帮我分析这份文件的内容"`

### 10. `smoke-file-upload.yaml` — 文件上传

- **name**: `smoke-file-upload`
- **description**: 验证文件上传和预览功能
- **target_url**: `{base_url}/login`
- **goal**: 登录后，从案件列表中选择第一个案件进入工作区，上传文件并验证文件可见可预览
- **assertions**:
  - 文件浏览区正常加载
  - 点击上传按钮弹出上传对话框
  - 上传测试文件成功，无错误
  - 文件出现在文件列表中，文件名与上传文件一致
  - 点击文件后预览区域有内容渲染
- **max_steps**: 25
- **timeout_seconds**: 90
- **test_data**:
  - `credentials: {email: "file-upload@test.com", password: "TestPass123!"}`
  - `case_id: "auto"`
  - `upload_file: "assets/files/test-upload.pdf"`

### 11. `smoke-file-browse.yaml` — 文件浏览与管理

- **name**: `smoke-file-browse`
- **description**: 验证文件浏览、文件夹操作、文件重命名和删除
- **target_url**: `{base_url}/login`
- **goal**: 登录后，从案件列表中选择第一个案件进入工作区，验证目录树展示、新建文件夹、重命名、删除等文件管理操作
- **assertions**:
  - 文件目录树正常展示（至少有一个目录节点）
  - 创建新文件夹后该文件夹名称出现在目录中
  - 重命名文件夹后旧名称消失、新名称出现
  - 删除文件夹后该项从目录消失
  - 操作过程中无可见错误提示
- **max_steps**: 30
- **timeout_seconds**: 90
- **test_data**:
  - `credentials: {email: "file-browse@test.com", password: "TestPass123!"}`
  - `case_id: "auto"`
  - `new_folder_name: "测试文件夹"`
  - `rename_folder_to: "重命名文件夹"`

### 12. `smoke-settings.yaml` — 设置页面

- **name**: `smoke-settings`
- **description**: 验证主题切换、密码修改和退出登录功能
- **target_url**: `{base_url}/login`
- **goal**: 登录后进入设置页面，测试主题切换、密码修改、退出登录，最后将密码改回原值以保持账号可用
- **assertions**:
  - 设置页面正常加载
  - 主题选项可见，切换到深色主题后页面背景色发生变化
  - 切换回浅色主题后背景色恢复
  - 密码修改表单可用，提交后有成功提示
  - 用新密码退出并重新登录成功
  - 将密码改回原值并确认成功
  - 退出登录后 URL 跳转到 /login
- **max_steps**: 30
- **timeout_seconds**: 90
- **test_data**:
  - `credentials: {email: "settings-{timestamp}@test.com", password: "TestPass123!"}`
  - `new_password: "NewTestPass123!"`

---

## 用户旅程场景详细设计

### 13. `journey-new-user.yaml` — 新用户完整体验

- **name**: `journey-new-user`
- **description**: 模拟全新用户从注册到首次使用的完整旅程
- **target_url**: `{base_url}/register`
- **goal**: 注册新账号，创建第一个案件并完成问卷，经过欢迎页进入工作区，确认初始评估触发
- **assertions**:
  - 注册成功后 URL 变为 /cases（自动登录）
  - 案件列表为空状态（无案件卡片）
  - 新建案件并完成问卷，提交后 URL 离开 /cases/new
  - 简历文件名在上传后出现在页面上
  - 欢迎页显示品牌信息文本
  - URL 变为 /cases/:id 格式（进入主工作区）
  - 出现"正在生成"状态后 90 秒内收到 AI 回复（文本长度 > 0）
  - Todo 进度面板可见
  - 全程无可见错误提示、无白屏
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
- **goal**: 登录后从案件列表选择第一个案件进入，与 AI 对话，上传文件后带附件继续对话，查看 Todo 进度
- **assertions**:
  - 登录后 URL 变为 /cases，案件列表有内容
  - 点击案件后进入工作区，聊天区域可见
  - 发送消息后 60 秒内收到 AI 回复（回复文本长度 > 0）
  - 上传文件成功，文件名出现在文件列表中
  - 带附件发送消息后 AI 回复文本长度 > 0
  - Todo 进度面板可见
  - 刷新页面后之前的消息仍然可见
  - 全程无可见错误提示或超时提示
- **max_steps**: 45
- **timeout_seconds**: 240
- **test_data**:
  - `credentials: {email: "journey-workflow@test.com", password: "TestPass123!"}`
  - `case_id: "auto"`
  - `message: "请帮我分析一下我的材料准备情况"`
  - `upload_file: "assets/files/test-doc.pdf"`
  - `message_with_file: "请查看我上传的这份推荐信，帮我评估一下"`

### 15. `journey-file-management.yaml` — 材料整理流程

- **name**: `journey-file-management`
- **description**: 模拟用户集中整理案件材料的完整流程
- **target_url**: `{base_url}/login`
- **goal**: 登录后从案件列表选择第一个案件进入，创建文件夹结构，上传文件，预览、重命名、删除
- **assertions**:
  - 创建 test_data 中指定的文件夹后，这些文件夹名称出现在目录中
  - 上传文件成功，文件名出现在文件列表中
  - 点击文件后预览区域有内容渲染
  - 重命名文件夹后旧名称消失、新名称出现
  - 删除文件后该文件从列表消失
  - 全程无可见错误提示
- **max_steps**: 40
- **timeout_seconds**: 180
- **test_data**:
  - `credentials: {email: "journey-files@test.com", password: "TestPass123!"}`
  - `case_id: "auto"`
  - `folders: ["推荐信", "获奖材料", "媒体报道"]`
  - `upload_files: ["assets/files/rec-letter.pdf", "assets/files/award.pdf"]`
  - `rename_folder_to: "推荐信-已整理"`

---

## 通用检测要求

所有场景的 goal 描述中应隐含以下检测（基于页面可见状态，不依赖浏览器控制台）：

1. **页面级**：无白屏（页面有可见内容）、无 404/500 错误页、页面标题非空
2. **交互级**：按钮点击后有可见变化、表单提交后有反馈（成功提示或跳转）、加载状态最终消失
3. **数据一致性**：创建的数据出现在列表中、删除的数据从列表消失、修改的数据更新正确
4. **网络健壮性**：API 调用在合理时间内有响应（无长时间"正在加载"卡死）、超时时有可见提示

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

# 按前缀批量运行
for f in config/scenarios/smoke-*.yaml; do python main.py "$f"; done
for f in config/scenarios/journey-*.yaml; do python main.py "$f"; done
```

## 范围外（后续迭代）

以下功能有意不包含在本次场景设计中，可根据需要在后续迭代中添加：

- 忘记密码 / 邮件验证流程（产品暂无此功能）
- 会话过期 / Token 失效后的重新登录体验
- 多案件间快速切换
- 欢迎页独立冒烟测试（已在 `smoke-case-create` 和 `journey-new-user` 中间接覆盖）
- 前端路由 404 页面测试
- 无障碍（a11y）专项测试
- 性能基准测试（页面加载时间阈值等）
- 多浏览器 / 移动端兼容性测试
