# 开门清点工位

## 0. 工位定位

开门清点由主理人亲自执行，不委派给 subagent。

这一站只做一件事：把顾客给出的本地文档或电子书变成后续工位能读、能找、能追溯的 Markdown 材料。它不做需求访谈，不抽洞见，不规划产品形态。

合格状态是：材料来源清楚，转换路径清楚，Markdown 副本读得到，失败原因说得明白，`sources/source-manifest.md` 能让验料工位从正文开始工作。

这一站真正要防的是三类假通过：脚本显示成功，但 Markdown 里没有可连续阅读的正文；材料能打开，但来源、版本或转换路径说不清；顾客给的是在线入口，却被误当成本地材料送进生产。开门清点只裁决材料能不能进入验料，不提前判断材料有没有洞见。

## 1. 工作步骤

1. **确认本轮正文材料**。只判断它是不是本轮要处理的主材料、是否可访问、有没有权限、损坏或范围不清的问题。若顾客只给网页、公众号、YouTube、在线文章、网页合集或其他 URL，请他先提供 PDF、EPUB、Word、Markdown、TXT 或其他本地文档 / 电子书副本。

2. **统一进入 Markdown**。如果材料已经是 Markdown 或纯文本，也复制或规范到 `sources/markdown/`；如果不是 Markdown，用 `scripts/convert-source-to-md.py` 转换。不要把原始路径直接交给验料工位。

3. **按材料类型选择转换路径**。
   - `.md`、`.markdown`、`.txt`：用 `convert-source-to-md.py` 规范到 `sources/markdown/`；乱码、正文过短或像摘要/索引时，检查编码和源材料。
   - 普通 PDF 或可复制文字 PDF：先用 `convert-source-to-md.py`；只抽到元信息、封面或目录时转 OCR；双栏、脚注、表格污染严重时标记质量问题。
   - 扫描 PDF 或图片页：先做一次默认 PDF 快检；确认无可抽取正文后，用 `scripts/ocr-pdf-to-md.py`。缺 OCR 环境时加 `--install-deps`。
   - Word、PPT、Excel、EPUB、CSV、JSON：用 `convert-source-to-md.py`，再抽样看阅读顺序、标题层级、表格和注释是否盖过主体。
   - 损坏文件或权限不足材料：记录来源和错误信息，不硬转；能换格式就请顾客换格式，能授权就请顾客授权。

4. **运行标准脚本**。转换默认使用：

```bash
python scripts/convert-source-to-md.py SOURCE_PATH sources/markdown/NAME.md
```

扫描 PDF 或图片页 fallback 使用：

```bash
python scripts/ocr-pdf-to-md.py SOURCE.pdf sources/markdown/NAME.md
```

本机缺 OCR 环境时使用：

```bash
python scripts/ocr-pdf-to-md.py --install-deps SOURCE.pdf sources/markdown/NAME.md
```

这些脚本都在本 skill 的 `scripts/` 目录下。运行时站在 skill 目录，或使用绝对路径。不要为了绕过一次失败临时创建第二套转换脚本。

5. **抽样验读 Markdown**。至少看开头正文、中段正文和结尾正文。脚本成功只说明生成了文件，不说明材料可用。抽样必须确认有连续段落、标题和主体内容，不是封面、目录、乱码、空壳、导航、广告、登录提示、OCR 残片或严重错序页面。

   开头样本看材料是否真正进入正文，不是封面、版权页、目录或网页导航；中段样本看论述、叙事或资料是否连续，页序和段落没有明显断裂；结尾样本看是否仍有主体内容，而不是索引、广告、参考文献污染或 OCR 垃圾。

6. **判定可读状态**。可读、部分可读和不可读不是情绪判断，而是给下游的通行信号：
   - 可读：Markdown 有足够连续正文，来源和 Markdown 路径清楚，验料可以从正文开始。
   - 部分可读：有一部分正文可用，但存在缺页、错序、图表缺失、OCR 瑕疵或章节缺口；必须把可用范围和风险写清，让验料知道哪里能读、哪里不能外推。
   - 不可读：正文缺失、乱码、严重 OCR 碎片、只有元信息 / 目录 / 登录提示，或材料权限不足、损坏到无法确认主体内容。

7. **失败分流**。默认转换失败时先重跑或换输出名排除路径问题；可复制文字抽不出正文时转 OCR；OCR 仍低质或材料损坏时标记不可用；权限、缺页、在线入口或版本不确定时回顾客补材料或授权。不要把失败材料伪装成部分可读。

8. **写来源记录**。把可用材料、失败材料和边界写入 `sources/source-manifest.md`。复杂缺口写在记录里，不散落在会话里。

## 2. 来源记录

`sources/source-manifest.md` 至少记录：

- `source_id`：稳定编号。
- `source_type`：PDF、EPUB、Word、Markdown、TXT、PPT、Excel、图片等。
- `original_path`：原始文件路径。
- `file_size`：本地文件大小。
- `conversion_route`：默认路径、OCR fallback、顾客提供文本等。
- `markdown_path`：Markdown 副本路径。
- `readable_status`：可读 / 部分可读 / 不可读。
- `sample_evidence`：抽样看到的正文证据，用一句话说明。
- `boundary_or_next_step`：缺页、权限、OCR 质量、需顾客补材料等。

来源记录只承接材料确认、转换和可读证据。不要在开门清点阶段记录章节、页码、标题层级、block、Markdown 起止行、KeyN、材料单元或产品形态判断；这些留给验料和规划。

## 3. 出站前自检

- 材料是否已经有可读 Markdown 副本。
- `sources/source-manifest.md` 是否能让验料工位找到正文。
- 不可读材料是否写清失败原因和下一步。
- 在线材料是否已经回顾客侧补本地副本。
- 抽样验读是否看过开头、中段和结尾正文。

## 4. 禁止

- 不要只看文件名或脚本成功提示就判断材料可用。
- 不要把不可读材料交给验料工位。
- 不要跳过 `sources/markdown/` 统一入口。
- 不要抓取 URL、转写音视频或绕过登录墙、验证码、付费墙。
- 不要把开门清点做成结构抽取或产品规划。
