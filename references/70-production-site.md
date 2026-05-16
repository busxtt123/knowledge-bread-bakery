# 70 项目现场

## 0. 核心结论

项目现场是面包房的工作台，服务协作、追溯、续接和返炉，不是管理装饰。复杂知识产品尤其要保留正文总稿、创作者 soul、创作日记和主理人工作记录。没有这些文件，下一位同事只能凭印象续写，作品会越来越平。

正式开工后，必须创建项目现场。不要在顾客还没说清楚前忙着建文件夹；主理人先完成接单、访谈和需求配方，再支起案台。

如果顾客指定了文件夹，就在那里开工；如果没有特殊要求，就在当前文件夹下创建一个清楚命名的本单文件夹，再建 `sources/`、`workspace/`、`delivery/`。

任务文件夹命名统一但不要繁琐：推荐 `YYYYMMDD-短主题`，例如 `20260512-ai-learning-guide` 或 `20260512-自我关怀长文`。短主题只保留便于查找的核心词，不写完整需求、不写长句、不暴露敏感信息。

材料转换 SOP 写在 `references/agents/00-kitchen-starter.md`。项目现场只记录本轮采用了哪些来源、材料当前是否可读；新的长期转换经验直接沉淀回开门清点 SOP 或脚本说明，不在生产现场另建备忘线。


## 1. 项目结构

```text
YYYYMMDD-短主题/
  README.md
  sources/
    source-manifest.md
    raw/                    # 可选，原始资料或副本
    markdown/               # 统一转换后的 md 材料，供后续工位读取
  workspace/
    need-recipe.md           # 需求配方：顾客为什么来、信息源、材料可读状态、吸收成功标准
    structure-extraction.md  # 验料：材料单元、洞见概览、论证地图、KeyN、材料位置
    creation-soul.md         # 创作者 soul：本炉创作面包师的第一人称存在底色
    course-plan.md           # 配方：课程 / 作品规划、认知地图、前置内容规划、原文材料包，可直接派工
    manuscript.md            # 正文总稿，一个文件续写
    creation-calendar.md     # 创作日记，一个文件续写；不作为主理人品尝依据
    project-log.md           # 主理人工作记录：创作者沟通、品尝判断、返炉和接续判断
  delivery/
    final.md
    final.pdf
```

## 2. 文件职责

- `README.md`：当前状态、本轮目标、最终成品路径、下一步。
- `sources/source-manifest.md`：来源清单、材料种类、文件大小、原始路径、Markdown 副本路径、转换状态、可读状态和来源边界。不要记录章节、页码、标题层级、block 或 Markdown 起止行；这些由验料 / 结构抽取站专门完成。
- `sources/raw/`：可选，保存原始资料或副本。
- `sources/markdown/`：统一转换后的 Markdown 材料，是验料、配方和创作的默认读取入口。
- `workspace/need-recipe.md`：具体顾客、今天为什么来、材料入口与信息源、材料可读状态、当前缺口、吸收成功标准。
- `workspace/structure-extraction.md`：材料单元、洞见概览、论证地图、KeyN / 关键命题、核心命题、材料位置。
- `workspace/creation-soul.md`：从材料气质中召唤出的第一人称创作面包师，不是作者传记；创作者要当真，正文不能泄漏设定。
- `workspace/course-plan.md`：讲次 / 切片规划、整体认知地图、前置内容规划、最后一讲结课地图安排；每讲绑定材料位置和原文材料包，可直接派工。
- `workspace/manuscript.md`：正文总稿，逐讲续写，不默认拆成多个孤立文件。
- `workspace/creation-calendar.md`：创作日记，创作者记录想法、规划、感受、犹疑和创作预感；没有格式和字数要求，不作为主理人通过 / 不通过依据。
- `workspace/project-log.md`：主理人工作记录，也是创作者写给主理人的沟通入口；回炉请求、规划修改建议、偏离规范的理由、不确定处、交接提醒、故障接管信息、主理人的品尝通过 / 不通过判断、返炉理由和下一讲接续判断都写这里。不另开独立品尝文件。
- `delivery/final.md`：最终交付源稿。
- `delivery/final.pdf`：默认手机阅读友好 PDF。
