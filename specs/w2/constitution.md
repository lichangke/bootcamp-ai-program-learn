这是针对 ./w2/db_query 项目的:

- 后端使用 Ergonomic Python 风格来编写代码，前端使用typescript。
- 前端后端要有严格的类型标注
- 使用 pydantic 来定义数据类型
- 所有后端生产的 json 数据，使用 camlCase 格式
- 不需要 authentication，任何用户都可以使用。