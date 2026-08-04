# services/rootcause — Python 根因定位引擎

职责：
- 启发式根因定位：baseline vs current 窗口，特征影响度量排序（Δ mean/std、PSI）
- 分层对比：group-by 子群（user bucket、region）差异
- 输出 top-K 可疑特征 + 置信度，生成可解释报告（JSON 导出）
