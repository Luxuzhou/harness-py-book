# 第3章 三轮安全实验 Demo

本目录是第3章"Agent循环与约束层"的完整配套代码。
来自公众号文章《200行Python，三轮博弈，把AI Agent关进笼子》的实战demo。

## 三种运行模式

```bash
# 第一轮：裸Agent，零防护（需要API key）
python run_bare.py

# 第二轮：加安全层的Agent（需要API key）
python run_harnessed.py

# 三轮渐进实验（需要API key，自动跑三轮并对比）
python run_progressive.py
```

## 不需要API的验证

```bash
# 验证安全层拦截能力（纯本地，不调用API）
python verify_safety.py
```

## 环境准备

```bash
# 安装额外依赖（在主仓库虚拟环境中）
pip install openai pyyaml

# 配置API key（两种方式任选）
# 方式1：编辑config.yaml中的api_key字段
# 方式2：设置环境变量
export OPENAI_API_KEY=sk-your-deepseek-key
export OPENAI_BASE_URL=https://api.deepseek.com
```

## 预期结果

| 轮次 | 安全层 | Agent策略 | 拦截结果 |
|------|--------|----------|---------|
| 第一轮 | 无 | 直接创建目录+执行危险操作 | 0次拦截 |
| 第二轮 | v1（路径+命令） | 写脚本间接绕过 | 0次拦截 |
| 第三轮 | v2（+内容扫描+脚本守卫） | 三次尝试均被拦截 | 3次拦截 |

## 文件说明

| 文件 | 职责 |
|------|------|
| agent.py | 最小Agent循环（DeepSeek API调用） |
| safety.py | 安全层（路径白名单+命令黑名单+内容扫描+脚本守卫） |
| tools.py | 4个工具（read_file/write_file/run_command/list_directory） |
| context.py | 上下文层（项目规则+文件摘要组装） |
| recovery.py | 恢复层（重试+超时+安全模式回退） |
| harness.py | 完整Harness（组装安全+上下文+恢复层） |
| config.yaml | 配置文件 |
| target_project/ | 实验用的目标项目 |
| verify_safety.py | 安全层本地验证（不需要API） |
