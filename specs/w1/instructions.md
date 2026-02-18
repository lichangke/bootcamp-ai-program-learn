# Instructions

## project alpha 需求和设计文档

构建一个简单的，使用标签分类和管理 ticket 的工具。它基于 postgres 数据库，使用 python fast API 作为后端，使用typescript/vite/tailwind/shadcn 作为前端。无需用户系统，当前用户可以：

项目代码统一放在 `./w1/project-alpha` 目录下。

- 创建/编辑/删除/完成/取消完成 ticket
- 编辑/删除 ticket 的标签
- 按照不同的标签查看 ticket 列表
- 按 title 搜索ticket

按照这个想法，帮我生成详细的需求和设计文档，放在 ./specs/w1/001-spec.md 文件中，输出为中文。

## implementation plan

按照 ./specs/w1/001-spec.md 中的需求和设计文档，生成一个详细的实时计划，放在 ./specs/w1/002-implementation-plan.md 文件中，输出为中文。
计划中的目录与路径约定同样以 `./w1/project-alpha` 为准。

## seed sql

添加一个seed.sql里面放50个meaningful 的 ticket 和几十个tags(包含platform tag,如 ios,projecttag如 viking,功能性 tag如autocomplete,等等)。要求 seed文件正确可以通过psql执行。

## 
按照 apple website 的设计风格,think ultra hard,优化 UI和UX。