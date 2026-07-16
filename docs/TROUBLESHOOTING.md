# 常见问题与排错

本文档根据书籍附录 D 整理。排错时先确认当前目录、Python 环境、API 配置和 Git 状态：

```powershell
pwd
python --version
python -m pip --version
git status --short
```

## 依赖缺失

出现 `ModuleNotFoundError` 时，通常是没有激活虚拟环境或没有安装第 10 章案例依赖：

```powershell
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pip install -r cases\data_compliance\target_service\requirements.txt
```

## API 调用失败

遇到 `OPENAI_API_KEY is not set`、401 或连接错误时：

1. 从 `.env.example` 复制 `.env`。
2. 填写 `OPENAI_BASE_URL`、`OPENAI_API_KEY` 和 `OPENAI_MODEL`。
3. 确认网络可以访问对应模型服务。

不要把 `.env` 内容粘贴到公开 Issue，也不要提交到 Git。

## Windows 中文或路径问题

PowerShell 下可使用反斜杠路径。控制台中文乱码时尝试：

```powershell
chcp 65001
$env:PYTHONUTF8=1
```

Session JSONL、日志和 Markdown 默认按 UTF-8 处理。

## 测试结果与书中不同

常见原因包括案例依赖未安装、从错误目录运行、实战已修改代码或 pytest 缓存干扰。推荐从仓库根目录运行：

```powershell
python -B -m pytest tests -q -p no:cacheprovider
python -B -m pytest cases\data_compliance\target_service\tests -q -p no:cacheprovider
```

如果服务读取了错误的根目录 `.env`，进入 `cases/data_compliance/target_service` 后运行 `python -B -m pytest tests -q`。

## `verify.py` 为什么失败

实战运行前，失败可能是故意保留的基线缺陷；Agent 运行中，失败是反馈信号；Agent 报告完成后仍失败，才表示没有通过验收。不要只看 Agent 的文字报告，应综合 `verify.py`、pytest、Maven 和 session 日志。

## 实战运行后 Git 变脏

这是第 9—11 章的预期行为。为了反复实验，请在运行前创建分支、Git 快照或案例副本。不要在不了解差异时提交运行产生的全部文件。

## Java 编译失败

确认 JDK 17 和 Maven 3.8+：

```powershell
java -version
mvn -version
cd cases\refactor_enterprise\target_project
mvn -DskipTests compile
```

如果已运行 Agent，代码可能停在中间状态；请从预设基线重新复现。

## 多 Agent 没有收敛

1. 确认第 9、10 章目标代码位于预设基线。
2. 确认 `cases/multiagent_enterprise/spec/api_contract.yaml` 未被实现角色私自修改。
3. 查看 `.harness_sessions/*.jsonl` 和角色交接产物。
4. 运行 `python -B cases\multiagent_enterprise\verify.py`，以验收脚本为准。

模型输出具有非确定性。复现时应关注最终验收、轮次与工具调用是否合理、Guard/Hook 反馈是否被处理，以及日志能否解释完整链路，而不是要求自然语言逐字一致。
