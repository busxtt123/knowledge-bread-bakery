# 开门清点工位

## 0. 工位

主理人站在案台前，先把顾客给出的本地文档和电子书变成后续同事能读、能找、能追溯的 Markdown 原料。这一站不委派给 subagent。它不做需求访谈，不抽洞见，也不替后面规划结构；它只判断一件事：这些材料能不能进厨房。

合格状态是：材料入口清楚，转换路径清楚，Markdown 副本读得到，失败原因说得明白，`sources/source-manifest.md` 能让验料同事从正文开始工作。

## 1. 操作流程

先根据顾客提供的本地路径或资料包清点材料。这个动作只回答三个问题：哪些是本轮要处理的正文材料，哪些只是背景，哪些因为权限、损坏或范围不清需要回头找顾客补。

这家面包房不转换网页，也不把音频、视频或在线内容转写成资料。公开网页、微信公众号、YouTube、在线文章、网页合集和其他 URL 都不进入开门清点。顾客给的是链接时，请他先提供 PDF、EPUB、Word、Markdown、TXT 或其他本地文档 / 电子书副本；拿到本地副本后，再按文档或电子书处理。

然后逐项检查材料格式。如果材料已经是 Markdown 或纯文本，也要复制或规范到 `sources/markdown/`，让后续工位从统一入口读取；如果不是 Markdown，就按材料类型转换成 Markdown。不要把原始路径直接交给验料同事。

本地文件默认用 `scripts/convert-source-to-md.py`。它的作用是把 PDF、EPUB、Word、TXT、Markdown、PPT、Excel、CSV、JSON 等文档和电子书统一落成 Markdown：

```bash
python scripts/convert-source-to-md.py SOURCE_PATH sources/markdown/NAME.md
```

OCR 只处理扫描件、图片页或默认 PDF 抽不出连续正文的情况。`scripts/convert-source-to-md.py` 如果只抽到元信息、封面或目录，会直接失败并提示转 OCR；`scripts/ocr-pdf-to-md.py` 是 fallback，不是普通 PDF 的默认入口：

```bash
python scripts/ocr-pdf-to-md.py SOURCE.pdf sources/markdown/NAME.md
```

如果本机还没准备 OCR 环境，可以显式加 `--install-deps`，让脚本先调用依赖准备器，再继续识别：

```bash
python scripts/ocr-pdf-to-md.py --install-deps SOURCE.pdf sources/markdown/NAME.md
```

所有转换产物放入 `sources/markdown/`。原始材料保留在 `sources/raw/` 或顾客指定位置。转换后必须抽样读正文，确认不是乱码、空壳、目录、样式碎片或错序页面；脚本成功只说明“生成了文件”，不说明“材料可用”。OCR 结果如果未通过脚本可读性判定，不能作为 Markdown 来源进入验料。

最后把每份材料写入 `sources/source-manifest.md`：原始路径、转换路线、Markdown 副本、可读状态、抽样证据和缺口。任何登录墙、验证码、付费墙、在线权限限制都不绕过；请顾客提供本地文档、电子书、授权副本或已经整理成文件的文本资料。

## 2. 材料转换 SOP

| 遇到什么材料 | 默认方案 | 错误或质量差时 | 什么时候停下来找顾客 |
|---|---|---|---|
| `.md` / `.markdown` / `.txt` | 用 `convert-source-to-md.py` 复制成规范 Markdown。 | 乱码时确认编码；正文太短时检查是否只是摘要、索引或空文件。 | 文件损坏、无法读取、顾客实际想用的不是这份文本。 |
| 普通 PDF / 可复制文字 PDF | 先用 `convert-source-to-md.py`。默认抽取通过脚本判定后，再继续抽样验读。 | 若脚本提示只抽到元信息、封面或目录，转 OCR；若双栏错序严重，先标记质量问题。 | 双栏、脚注、表格污染到无法追原文；优先请顾客给 EPUB、Word、单栏 PDF 或可复制文本。 |
| 扫描 PDF / 图片页 PDF | 先用默认 PDF 路径做一次快检；确认无可抽取正文后走 `ocr-pdf-to-md.py`。本机缺 OCR 环境时，用 `--install-deps` 让脚本先准备依赖。 | 调整 `--lang`、`--dpi`、`--first-page` / `--last-page` 小范围重跑，抽样看术语、人名、数字和页序。 | OCR 脚本判定不可读，或抽样发现大量错字、漏行、页序混乱、图片太糊；请顾客给更清晰扫描件或原始电子版。 |
| Word / PPT / Excel / EPUB / CSV / JSON | 用 `convert-source-to-md.py`。 | 抽样看阅读顺序、标题层级、表格和注释是否盖过主体。 | 转换后只有目录、样式、表格碎片或正文丢失；请顾客导出 Markdown、TXT、PDF 或正文。 |
| 已整理成文件的文稿 / 讲义 / 会议纪要 | 作为本地文本材料处理，用 `convert-source-to-md.py` 规范成 Markdown。 | 抽样看术语、关键数字、段落顺序和上下文是否连续。 | 只有音频、视频或在线链接，没有本地文档时不进入验料；请顾客先提供可读文件。 |
| 文件夹 / 资料包 | 先列清文件类型和优先级，再逐份转换；不要把整个目录一次性塞进脚本。 | 去重、标记重复版本、区分正文材料和附件材料。 | 材料范围不清、版本冲突、缺核心文件；回到顾客确认处理范围。 |
| 损坏文件 / 权限不足材料 | 记录入口和错误信息，不硬转。 | 能换格式就请顾客换格式，能授权就请顾客授权。 | 只要正文不可读，就不要交给验料同事。 |

## 3. 抽样验收

每份主要 Markdown 副本至少抽样三处：开头正文、中段正文、结尾正文。抽样不是读文件名，也不是看脚本成功提示，而是亲自确认有连续段落、标题和主体内容。

通过信号：

- 正文足够长，不只是标题、封面、目录、按钮、导航、广告或登录提示。
- 段落顺序大体可读，能定位到原始文件。
- 关键术语、人名、数字没有系统性错字。
- 失败边界清楚：知道是权限、扫描质量、格式损坏，还是源材料本来不足。

不通过时不要把材料送进验料。开门清点暴露缺口，是保护后面所有工位。

## 4. 来源清单字段

`sources/source-manifest.md` 至少记录：

- `source_id`：稳定编号。
- `source_type`：PDF、EPUB、Word、Markdown、TXT、PPT、Excel、图片、资料包等。
- `original_path`：原始文件路径。
- `file_size`：本地文件大小。
- `conversion_route`：默认入口、OCR fallback、顾客提供文本等。
- `markdown_path`：Markdown 副本路径。
- `readable_status`：可读 / 部分可读 / 不可读。
- `sample_evidence`：抽样看到的正文证据，用一句话说明。
- `boundary_or_next_step`：缺页、权限、OCR 质量、需顾客补材料等。

不要在开门清点阶段记录章节、页码、标题层级、block 或 Markdown 起止行；这些留给验料 / 结构抽取站。

## 5. 输出

直接写入 `sources/source-manifest.md`，不再回写 `workspace/need-recipe.md`。需求配方只保留顾客为什么来、材料入口和吸收成功标准；来源清单负责承接材料清点、转换和可读证据。

```markdown
# 来源清单

| source_id | source_type | original_path | file_size | conversion_route | markdown_path | readable_status | sample_evidence | boundary_or_next_step |
|---|---|---|---|---|---|---|---|---|
```

开门清点结束时，主理人在会话或主理人判断里说明：哪些材料已经可读，哪些材料不可读，下一站是否能进入验料。复杂缺口写入 `boundary_or_next_step`，不要散落在会话里。

## 6. 走偏气味

- 只看文件名，没有抽样读正文。
- 材料不可读却继续交给验料同事。
- 可转换来源没有落成 Markdown 副本。
- 看见 URL 就试图抓取网页，而不是请顾客提供本地文档或电子书副本。
- 把 PDF 默认抽取、OCR、电子书和普通文本材料混成一套模糊流程。
- 把开门清点做成结构抽取或产品规划。
