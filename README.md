# knowledge-bread-bakery

把一份本地长材料做成可开始、可理解、可吸收、可带走的知识作品。

许可证：MIT

## 前排提要

本 skill 的一次完整任务通常需要运行 1 小时左右，并且对上下文容量和连续性要求较高；实际消耗取决于原材料的体量、结构、可读质量和目标交付形态。

推荐使用 DeepSeek v4 系列运行该 skill。

把难啃的书籍变得顺滑，是本 skill 的主要功能；但它真正的价值，在于通过大模型定制按需知识，让知识变成一场好奇心的冒险。玩得开心！

## 适合什么

适合把一本书、一份 PDF / EPUB / Word / Markdown / TXT、长报告、课程草稿或已经整理成文件的文本资料，做成单篇长文、多讲课程或阅读路径。

它尤其适合材料本身很重要、普通摘要会把它压扁的场景。目标不是提炼几个要点，而是让读者多出一套可以反复调用的图式、语言或判断方式。

## 不适合什么

- 不抓取网页、公众号、公开视频、YouTube 页面或在线媒体。
- 不绕过访问权限；材料必须是本地可读文件或授权副本。
- 不承诺自动修复所有文件质量问题；扫描 PDF、缺页、乱码、错序材料需要先清点和验证。
- 不把过程文件当成默认交付物。
- 不替代医学、法律、财务等高影响主题的专业审阅。

## 交付物

一次完整生产通常会建立项目现场：

```text
project/
  sources/
  workspace/
  delivery/
```

`sources/` 保存来源和 Markdown 副本；`workspace/` 保存需求说明、结构抽取、规划、正文总稿、创作日记和主理人记录；`delivery/` 保存整理后的最终稿和 PDF。

默认交付是按成品标题命名的手机阅读友好 PDF。顾客明确要求 Markdown 时，可以同时交付 `delivery/final.md`。

## 怎么使用

运行时先读 `SKILL.md`。`SKILL.md` 是主理人 SOP，说明怎样接单、建现场、清点材料、委派工位、裁决出站、组织返工和完成交付。

使用时提供本地文件路径，例如：

```text
请用 knowledge-bread-bakery，把 C:\materials\book.pdf 做成一个 5 讲知识面包。
我想把这本书真正读进去，不想只要摘要。
默认交付移动端 PDF。
```

只给 URL 时，skill 会要求先提供本地副本。

## 文档结构

```text
knowledge-bread-bakery/
  SKILL.md                 # 主理人 SOP
  scripts/                 # 确定性辅助脚本
  tests/                   # 脚本和兼容性测试
  references/
    agents/                # 工位 SOP
    standards/             # 出站标准和返工方向
    souls/                 # 工位第一人称方向
    workflows/             # 跨阶段流程
    methods/               # 可复用方法
    recovery/              # 异常接管和恢复
    maintenance/           # skill 自身维护规则
```

脚本只负责确定性辅助能力，例如本地材料转 Markdown、OCR fallback 和 PDF 生成；作品判断由主理人和对应工位完成。

## 灵感来源

本项目的灵感来自《得到品控手册》中的课程制作经验、《故事》中的普遍形式，以及何同学的精彩视频。

## 许可证与致谢

本项目采用 MIT License。

本项目的本地材料转换能力接入了 Microsoft 的开源工具 [MarkItDown](https://github.com/microsoft/markitdown)，用于将 EPUB、Word、PDF、PPT、Excel 等本地文件转换为 Markdown。感谢 Microsoft 和 MarkItDown 项目提供稳定、通用的文档转换基础设施。

扫描版 PDF 的 OCR fallback 依赖 [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) 与 [Poppler](https://poppler.freedesktop.org/) 中的 `pdftoppm`：Poppler 负责把 PDF 页面渲染为图片，Tesseract 负责识别图片中的文字。感谢这些开源项目让本地扫描材料也能进入可读、可追溯的知识生产流程。

## 维护

修改这个 skill 前，先读：

```text
references/maintenance/how-to-integrate-new-philosophy.md
```

测试：

```bash
python -m unittest discover -s tests
```
