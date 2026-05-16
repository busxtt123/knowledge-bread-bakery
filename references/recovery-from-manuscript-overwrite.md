# 恢复被覆盖的 manuscript.md

## 0. 问题

逐讲创作依赖 `workspace/manuscript.md`、`workspace/creation-calendar.md` 和 `workspace/project-log.md`。如果任何执行者用整文件覆盖的方式写入，前文、创作状态或主理人沟通可能瞬间丢失。

覆盖事故的典型信号：

- 文件大小突然从数百 KB 变成几十 KB。
- 行数从数千行变成数百行。
- 前面讲次标题消失。
- 文件只剩最新一讲。
- 创作日记只剩最新记录，前面的创作状态消失。
- `project-log.md` 中的回炉请求、规划修改建议、不确定处或故障记录消失。

一旦怀疑覆盖，先停工。不要继续派下一讲，不要整理交付稿，也不要让另一个 subagent 接着写。

## 1. 先确认事故范围

在项目现场检查：

```bash
wc -l workspace/manuscript.md workspace/creation-calendar.md workspace/project-log.md
ls -lh workspace/manuscript.md workspace/creation-calendar.md workspace/project-log.md
rg -n "^#|^##|第.+讲|切片" workspace/manuscript.md
```

判断三件事：

- 丢的是正文、创作日记、主理人沟通，还是多者都丢。
- 从哪一讲开始丢的。
- 最近一次可相信的版本在哪里。

把事故判断写进 `workspace/project-log.md`。如果 `project-log.md` 也被覆盖，就先新建一段“事故记录”，说明它也是恢复对象。

## 2. 优先找备份

按优先级查找：

```bash
ls workspace/manuscript_backup_*.md
ls workspace/*.md.bak
ls delivery/*.md
ls delivery/*.pdf
```

如果有可信备份，先复制成新的恢复稿，不直接覆盖当前事故现场：

```bash
cp workspace/manuscript_backup_YYYYMMDD_HHMM.md workspace/manuscript.recovered.md
```

确认恢复稿包含丢失讲次后，再替换 `workspace/manuscript.md`。替换前保留事故版本：

```bash
cp workspace/manuscript.md workspace/manuscript.accident.md
cp workspace/manuscript.recovered.md workspace/manuscript.md
```

## 3. 没有备份时重建

没有完整备份，就按材料可靠性从高到低重建：

1. `delivery/final.md`：如果曾经整理过交付稿，优先从这里恢复正文。
2. subagent 返回内容：如果任务返回里包含完整正文，取回并核对位置。
3. `workspace/project-log.md`：用每讲品尝记录确认哪些讲已经通过、哪些需要重写；也用回炉请求、规划修改建议、不确定处和交接提醒恢复生产沟通。
4. `workspace/course-plan.md`：用切片规划重建结构。
5. `workspace/creation-calendar.md`：只能作为恢复创作者思路的辅助，不作为主理人验收依据。
6. `workspace/structure-extraction.md` 和原文：必要时回原料重写。

重建不是凭记忆补齐。每一讲都要重新确认：本讲在整炉里的作用、主料、入口判断、删掉的材料和出炉后留下什么。

## 4. 恢复后验收

恢复完成后，主理人亲自检查：

- 前面讲次标题都在。
- 最新讲没有丢。
- 正文顺序正确。
- 创作日记如存在，仍能帮助创作者接上状态。
- `project-log.md` 中主理人需要知道的回炉请求、规划修改建议、不确定处、故障记录和品尝通过记录没有丢。
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

## 5. 后续预防

后续不增加复杂流程，只守三条：

- 正文、创作日记和 `project-log.md` 只做增量追加或小范围补丁，不做整文件覆盖。
- 在关键节点备份一次正文、创作日记和 `project-log.md`：长项目完成一组自然讲次、进入大返工、进入交付整理，或主理人准备把现场交给另一个执行者时。
- 当前讲派工时写清：不得覆盖 `manuscript.md`、`creation-calendar.md` 和 `project-log.md`，只能续写或按明确位置补丁修改。

推荐备份：

```bash
cp workspace/manuscript.md workspace/manuscript_backup_$(date +%Y%m%d_%H%M).md
cp workspace/creation-calendar.md workspace/creation-calendar_backup_$(date +%Y%m%d_%H%M).md
cp workspace/project-log.md workspace/project-log_backup_$(date +%Y%m%d_%H%M).md
```

关键节点的轻量检查：

```bash
wc -l workspace/manuscript.md workspace/creation-calendar.md workspace/project-log.md
rg -n "^#|^##|第.+讲|切片" workspace/manuscript.md
```

备份不是为了增加流程感，而是为了让逐讲生产敢继续。连续作品一旦丢掉前文、创作状态或主理人沟通，后面就会从接现场变成猜。
