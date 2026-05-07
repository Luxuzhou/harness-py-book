# 任务：10 步 Python 工具库重构

你需要按顺序完成 10 个小步骤。每一步都需要修改文件。每完成一步，运行
`pytest test_step_<N>.py -v` 确认该步通过，然后更新 TASK.md 记录进度。

## 步骤清单

1. **拆分 `utils.py` 中的字符串工具**
   把 `slugify`、`camel_to_snake`、`truncate` 三个函数移到新文件
   `string_utils.py`，并在 `utils.py` 中保留 `from .string_utils import *`
   做兼容。

2. **拆分 `utils.py` 中的日期工具**
   把 `parse_iso`、`to_unix`、`format_duration` 三个函数移到新文件
   `date_utils.py`。

3. **为 `string_utils.py` 添加类型标注**
   为三个函数加上 Python 3.10+ 的类型标注（`str -> str`, `int -> str` 等）。

4. **为 `date_utils.py` 添加类型标注**
   同上。

5. **提取公共常量到 `constants.py`**
   把 `utils.py`、`string_utils.py`、`date_utils.py` 中的魔术数字（如
   `MAX_SLUG_LEN = 50`、`DEFAULT_TZ = 'UTC'`）统一移到 `constants.py`。

6. **添加 docstring**
   给 `string_utils.py` 和 `date_utils.py` 中的每个函数加 Google 风格
   的 docstring。

7. **重构 `truncate` 函数**
   `truncate` 当前硬编码省略号 `...`。改为接受可选参数 `suffix='...'`，
   并支持按词而非字符截断（参数 `word_boundary=False`）。

8. **添加 `slugify` 的多语言支持**
   当前 `slugify` 只处理 ASCII。添加参数 `lower=True` 和
   `allow_unicode=False`，当后者为 True 时保留中文字符。

9. **提取测试共用的 fixture**
   把各 `test_step_*.py` 中重复使用的 fixture 函数提取到 `conftest.py`。

10. **更新 README.md**
    在 README.md 中列出所有公开导出的函数清单，按 `string_utils` /
    `date_utils` / `constants` 分组。

## 进度记录

**每完成一步**，必须更新 TASK.md，格式：

```markdown
- [x] 步骤 1：拆分字符串工具（pytest 通过）
- [ ] 步骤 2：拆分日期工具
...
```

中断后恢复时，请先读取 TASK.md 了解已完成的步骤。
