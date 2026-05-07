# 项目指引

## 构建与验证
- 运行测试: `python -m pytest test_expected.py -v`

## 执行策略
- 先读源文件和测试，理解bug再动手
- 改完立即跑测试验证

## 禁令
- 不要修改 test_expected.py
- 不要新增第三方依赖
- 不要删除源文件中已有的异常检查（如 ValueError）
