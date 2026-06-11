# 70 项目现场

## 0. 建现场位置

本页只管建现场：主理人在需求说明通过后，把本单生产文件放到一个可追溯、可续接、可返工的位置。

材料转换看 `references/agents/00-kitchen-starter.md`；出站是否合格看 `references/standards/00-kitchen-start.md`。

## 1. 建现场时机

不要在顾客还没说清楚前忙着建文件夹。主理人先完成接单、前台需求和需求说明；需求说明达到出站状态后，再支起工作台。

如果顾客、当前项目或其他可靠信息指定了合适位置，就在那里开工。没有特殊要求时，在当前文件夹下创建一个清楚命名的本单文件夹。

文件夹命名推荐 `YYYYMMDD-短主题`。短主题只保留便于查找的核心词，不写完整需求、不写长句、不暴露敏感信息。

## 2. 最小结构

项目现场至少包含：

```text
YYYYMMDD-短主题/
  README.md
  sources/
    source-manifest.md
    raw/
    markdown/
  workspace/
    need-recipe.md
    structure-extraction.md
    course-plan.md
    manuscript.md
    creation-calendar.md
    project-log.md
  delivery/
    final.md
```

建好现场后，第一件事是把刚通过的需求说明写入 `workspace/need-recipe.md`。

## 3. 文件职责

- `README.md`：现场入口，只写本单主题、当前状态、主要材料、生产阶段和关键注意事项；不要写成过程日志，也不要替代 `project-log.md`。
- `sources/source-manifest.md`：来源、转换、可读状态和来源边界。
- `sources/raw/`：可选，保存原始材料或副本。
- `sources/markdown/`：统一转换后的 Markdown 材料，是验料、规划和创作默认读取位置。
- `workspace/need-recipe.md`：顾客为什么来、材料入口、材料可读状态、吸收成功标准。
- `workspace/structure-extraction.md`：材料单元、核心命题、论证地图、KeyN、风险与边界。
- `workspace/course-plan.md`：课程 / 作品规划、讲组设计、切片规划、材料包、前置内容与结课地图规划。
- `workspace/manuscript.md`：正文总稿，一个文件按顺序续写。
- `workspace/creation-calendar.md`：创作者连续性日记，不作为主理人出站依据。
- `workspace/project-log.md`：主理人裁决、创作者沟通、规划修订告知、返工、故障和接续判断。
- `delivery/final.md`：最终交付源稿。

## 4. 禁止

- 不要把过程文件散落到另一个顺手但不合适的目录。
- 不要让 `README.md` 承担需求说明、来源记录、主理人裁决或事故记录。
- 不要把材料转换经验写进现场备忘；长期经验沉淀回开门清点 SOP 或脚本说明。
- 不要在 `source-manifest.md` 写章节结构、KeyN、材料单元或产品形态判断。
- 不要默认把 `workspace/` 或 `sources/` 交付给顾客。
