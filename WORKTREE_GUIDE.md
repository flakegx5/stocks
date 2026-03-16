# Worktree Collaboration Guide

本项目使用 `git worktree` 并行维护三条核心开发线，避免多个 agent 或多个终端在同一目录里频繁切换分支。

## 目录结构

统一父目录：

- `<worktree-root>/main` -> `main`
- `<worktree-root>/data` -> `codex/data-pipeline`
- `<worktree-root>/indicators` -> `codex/indicators`
- `<worktree-root>/frontend` -> `codex/frontend`

约定：

- `main` 只用于集成、验收、最终合并
- `data` 负责原始数据抓取、更新链路、调度和数据质量修复
- `indicators` 负责指标计算、排序逻辑、构建管线和测试
- `frontend` 负责页面结构、样式、交互和前端加载性能

每个 worktree 都是完整仓库，不是手工复制的项目副本。

## 日常使用

进入对应目录工作，不要在同一个目录里反复切换分支。

```bash
cd <worktree-root>/data
git status
```

开发前先同步主线：

```bash
git fetch origin
git rebase origin/main
```

完成后正常提交：

```bash
git add -A
git commit -m "your change"
git push -u origin <current-branch>
```

首次推送时常用分支名：

- `codex/data-pipeline`
- `codex/indicators`
- `codex/frontend`

## 合并建议

- 公共基础改动优先尽快合回 `main`
- 其他 worktree 再各自同步 `origin/main`
- 如果三条线都需要改同一份公共文件，先拆出最小公共改动，减少后续冲突

推荐节奏：

1. 在对应 worktree 内完成单条任务
2. 本地验证通过
3. 合并到 `main`
4. 其他 worktree 执行 `git fetch origin && git rebase origin/main`

## 注意事项

- 不要手工复制整个项目做“隔离”
- 不要在 `main` 目录里直接做长期功能开发
- 不要让多个 agent 共享同一个 worktree 目录同时修改
- 若移动了 worktree 目录，需要执行 `git worktree repair`

## 新增或重建 worktree

如需重建，可在 `main` 目录执行：

```bash
git worktree add <worktree-root>/data -b codex/data-pipeline main
git worktree add <worktree-root>/indicators -b codex/indicators main
git worktree add <worktree-root>/frontend -b codex/frontend main
```

查看当前 worktree：

```bash
git worktree list
```

后续 agent 接手说明见 `AGENT_HANDOFF_WORKTREES_20260316.md`。
