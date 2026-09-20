# Zephyr 中文文档

这是 Zephyr Project 官方文档的中文机器翻译镜像，内容持续跟随上游 `main` 分支同步。

## 重要说明

- 本项目是独立的非官方中文翻译站点，不代表 Zephyr Project。
- 翻译由自动化流程生成，技术细节、命令和 API 使用前请以[官方英文文档](https://docs.zephyrproject.org/latest/)为准。
- Zephyr 文档及其衍生翻译遵循上游仓库中的 Apache-2.0 许可；版权和来源信息会保留在发布站点中。

## 本地构建

需要 Python、CMake、Ninja、Doxygen 和 Zephyr 的 west 工作区。完整流程由 GitHub Actions 执行：

```powershell
python tools/translate_rst.py --tree path/to/zephyr/doc --cache .cache/translation.json
make -C path/to/zephyr/doc html
```

默认翻译服务是 Google Translate 的公开接口封装。若接口限流，可以在工作流中替换为兼容的翻译服务；脚本使用缓存，重复运行不会重复提交已完成的句段。

## 许可证与来源

源文档来自 [zephyrproject-rtos/zephyr](https://github.com/zephyrproject-rtos/zephyr)，上游版本、许可证和版权信息在每次构建时保留。请参阅 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。
