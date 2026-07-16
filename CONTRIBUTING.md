# 贡献指南

感谢你帮助改进《驾驭 AI：Harness Engineering 实战》的配套代码。

## 提交问题

请说明使用的操作系统、Python 版本、运行命令、完整错误信息，以及问题对应的章节。不要在 Issue、日志或截图中提交 API Key、真实患者数据或其他敏感信息。

## 提交代码

1. 从 `main` 创建分支，并让一次提交只解决一个主题。
2. 保持示例与对应章节的叙述一致；修改章节入口时同步更新 `README.md` 和 `docs/CHAPTER_INDEX.md`。
3. 不要提交 `.env`、`.harness_sessions/`、运行日志、构建目录或真实业务数据。
4. 提交前至少运行：

```powershell
python -B -m pytest tests -q -p no:cacheprovider
python -B -m pytest cases\data_compliance\target_service\tests -q -p no:cacheprovider
```

涉及第 9 章 Java 项目时，还应在 `cases/refactor_enterprise/target_project` 下运行 `mvn -DskipTests compile`。涉及第 9—11 章实战逻辑时，请运行相应目录中的 `verify.py`。

## 内容边界

本仓库接受代码、测试、示例和配套技术文档的修正。书稿正文及出版内容不在本仓库的 MIT 许可证范围内。
