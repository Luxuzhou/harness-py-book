# 环境准备与实验命令

本文档根据书籍附录 C 整理。推荐使用 Windows 10/11、macOS 或 Linux，Python 3.10+；第 9 和第 11 章还需要 JDK 17 与 Maven 3.8+。

## Python 环境

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pip install -r cases\data_compliance\target_service\requirements.txt
```

macOS / Linux：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -r cases/data_compliance/target_service/requirements.txt
```

## 模型 API

复制 `.env.example` 为 `.env`，填写自己的 OpenAI 兼容接口信息。不要提交 `.env`。

```text
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=deepseek-chat
```

第 3—8 章和第 12 章的基础示例大多不需要 API；第 9—11 章实战需要 API。

## 健康检查

```powershell
python verify_env.py
python -B -m pytest tests -q -p no:cacheprovider
python -B -m pytest cases\data_compliance\target_service\tests -q -p no:cacheprovider
```

出版基线的预期结果分别是根测试 `89 passed`、第 10 章服务测试 `137 passed`。

## 章节示例

```powershell
python -B examples\ch03_safety_demo.py
python -B examples\ch04_tools.py
python -B examples\ch04_mcp_server.py --test
python -B examples\ch05_context.py
python -B examples\ch06_memory.py
python -B examples\ch07_verify.py
python -B examples\ch08_feedback.py
python -B examples\ch12_observe.py
```

## 实战与验收

```powershell
# 第 9 章
python -B cases\refactor_enterprise\run.py
python -B cases\refactor_enterprise\verify.py

# 第 10 章
python -B cases\data_compliance\run.py
python -B cases\data_compliance\verify.py

# 第 11 章
python -B cases\multiagent_enterprise\run.py
python -B cases\multiagent_enterprise\verify.py
```

Java 项目可单独编译：

```powershell
cd cases\refactor_enterprise\target_project
mvn -DskipTests compile
```

推荐先运行根测试和无 API 示例，再安装案例依赖并运行第 10 章测试，最后从干净 Git 基线依次复现实战。`run.py`、`verify.py` 和单元测试含义不同：前者启动 Agent 并可能改代码，后两者负责验证结果。
