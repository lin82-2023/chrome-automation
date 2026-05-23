# chrome-research

基于 chrome-agent-core 的多源研究 Agent：

- 用户输入主题 → LLM 规划子任务 → 顺序执行多网站调研 → 综合生成报告
- 内置超时保护、错误自愈、数据质量校验
- CLI 入口：`chrome-research`

详见根目录 [README](../../README.md) 与 [ARCHITECTURE](../../ARCHITECTURE.md)。
