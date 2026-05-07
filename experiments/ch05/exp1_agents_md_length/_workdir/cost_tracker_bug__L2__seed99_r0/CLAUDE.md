# 项目指引

## 项目性质

这是一个独立的 Python 单文件任务。每个任务目录包含一个有 bug 的源文件和一份预期测试。
目标是修复 bug，让所有测试通过。

## 构建与验证

- 运行测试: `python -m pytest test_expected.py -v`
- 单个测试: `python -m pytest test_expected.py::<test_name> -v`
- 检查语法: `python -c "import <module_name>"`

## 项目结构

```
<工作目录>/
  <module>.py        # 有 bug 的源文件（需要修改）
  test_expected.py   # 预期测试（禁止修改）
```

一个任务目录下通常只有这两个文件，不存在多模块依赖。

## 编码规范

- Python 3.10+，保留源文件已有的类型注解风格
- 不要引入第三方依赖，标准库足够
- 保留原有的 docstring 风格
- 异常处理：保留源文件中已有的异常检查逻辑，不要擅自移除

## 执行策略

1. 先用 read_file 读取源文件和 test_expected.py，理解当前行为和期望行为的差距
2. 定位 bug 所在的具体行，而不是整段重写
3. 修改后立即运行 pytest 验证
4. 如果某个测试仍失败，再读错误信息精确修正，不要推倒重来

## 禁令

- 不要修改 test_expected.py（这是评测基准）
- 不要引入第三方依赖（requests、pandas 等均禁止）
- 不要使用 print 调试，通过运行测试来验证假设
- 不要删除源文件中已有的参数校验或异常抛出逻辑
- 不要在修复过程中改变函数的公开签名
- 不要重命名类或函数
