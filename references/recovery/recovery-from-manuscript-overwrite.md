# 恢复被覆盖的 manuscript.md

## 0. 事故位置

本页只处理正文或关键现场文件疑似被覆盖后的恢复。正常创作、正常备份和出站裁决不在这里展开。

一旦怀疑覆盖，先停工。不要继续派下一讲，不要整理交付稿，也不要让另一个 subagent 接着写。

## 1. 覆盖信号

- `workspace/manuscript.md` 文件大小或行数突然大幅变小。
- 前面讲次标题消失。
- 文件只剩最新一讲。
- `workspace/creation-calendar.md` 只剩最新记录。
- `workspace/project-log.md` 丢失规划修订告知、主理人裁决、不确定处或故障记录。

## 2. 确认事故范围

先亲自打开三个文件：`workspace/manuscript.md`、`workspace/creation-calendar.md` 和 `workspace/project-log.md`。不要只看工具输出；事故判断要来自正文上下文、讲次顺序、创作日记和主理人记录是否还互相对得上。

需要辅助检查时，看文件大小、行数、文件开头、文件结尾和目录骨架即可：

```bash
wc -l workspace/manuscript.md workspace/creation-calendar.md workspace/project-log.md
ls -lh workspace/manuscript.md workspace/creation-calendar.md workspace/project-log.md
head -n 40 workspace/manuscript.md
tail -n 80 workspace/manuscript.md
```

判断：

- 丢的是正文、创作日记、主理人沟通，还是多者都丢。
- 从哪一讲开始丢。
- 最近一次可信版本在哪里。

把事故判断写入 `workspace/project-log.md`。如果 `project-log.md` 也被覆盖，先新建一段事故记录，说明它也是恢复对象。

## 3. 优先找备份

按顺序找：

```bash
ls workspace/manuscript_backup_*.md
ls workspace/*.md.bak
ls delivery/*.md
ls delivery/*.pdf
```

找到可信备份时，先复制成恢复稿，不直接覆盖事故现场：

```bash
cp workspace/manuscript_backup_YYYYMMDD_HHMM.md workspace/manuscript.recovered.md
```

确认恢复稿包含丢失讲次后，再替换 `workspace/manuscript.md`。替换前保留事故版本：

```bash
cp workspace/manuscript.md workspace/manuscript.accident.md
cp workspace/manuscript.recovered.md workspace/manuscript.md
```

## 4. 没有备份时重建

没有完整备份时，按可靠性从高到低重建：

1. `delivery/final.md`：如果曾经整理过交付稿，优先从这里恢复正文。
2. subagent 返回内容：如果任务返回里包含完整正文，取回并核对位置。
3. `workspace/project-log.md`：确认哪些讲已经通过、哪些需要重写。
4. `workspace/course-plan.md`：用切片规划重建结构。
5. `workspace/creation-calendar.md`：只作为恢复创作者思路的辅助。
6. `workspace/structure-extraction.md` 和原文：必要时回材料重写。

重建不是凭记忆补齐。每一讲都要重新确认本讲位置、核心材料、局部图式和出站状态。

## 5. 恢复后验收

恢复后主理人亲自检查：

- 前面讲次标题都在。
- 最新讲没有丢。
- 正文顺序正确。
- 创作日记如存在，仍能帮助创作者接上状态。
- `project-log.md` 中主理人需要知道的裁决、返工、规划修订和故障记录没有丢。
- 文件大小和行数回到合理范围。

检查通过后，在 `project-log.md` 追加事故记录：

```markdown
## 覆盖事故记录

- 发现时间：
- 事故信号：
- 影响文件：
- 丢失范围：
- 恢复来源：
- 已验证：
- 后续预防：
```

## 6. 后续预防

后续不增加复杂流程，只守三条：

- 正文、创作日记和 `project-log.md` 只做增量追加或小范围补丁，不做整文件覆盖。
- 长项目完成一组自然讲次、进入大返工、进入交付整理，或准备交给另一个执行者时，备份正文、创作日记和 `project-log.md`。
- 当前讲或讲组派工时写清：不得覆盖 `manuscript.md`、`creation-calendar.md` 和 `project-log.md`，只能续写或按明确位置补丁修改。

推荐备份：

```bash
cp workspace/manuscript.md workspace/manuscript_backup_$(date +%Y%m%d_%H%M).md
cp workspace/creation-calendar.md workspace/creation-calendar_backup_$(date +%Y%m%d_%H%M).md
cp workspace/project-log.md workspace/project-log_backup_$(date +%Y%m%d_%H%M).md
```

关键节点的轻量检查：

```bash
wc -l workspace/manuscript.md workspace/creation-calendar.md workspace/project-log.md
head -n 40 workspace/manuscript.md
tail -n 80 workspace/manuscript.md
```

备份不是为了增加流程感，而是为了让逐讲生产敢继续。连续作品一旦丢掉前文、创作状态或主理人沟通，后面就会从接现场变成猜。
