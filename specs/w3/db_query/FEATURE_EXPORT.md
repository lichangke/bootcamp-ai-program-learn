# 查询结果导出（CSV / JSON）设计思路

## 1. 功能定位

查询结果导出能力是一个**前端本地导出功能**，用于将“已执行 SQL 后拿到的结果集”下载为文件：

- `EXPORT CSV`
- `EXPORT JSON`

该能力出现在主页面 `App` 的 `RESULTS` 卡片右上角。

## 2. 代码入口与所在层

### 2.1 前端主入口

- 应用入口：`w2/db_query/frontend/src/main.tsx`
- 实际页面：`w2/db_query/frontend/src/App.tsx`

导出相关逻辑全部集中在 `App.tsx`：

- 按钮渲染：`RESULTS` 卡片 `extra` 区域
- 点击处理：`exportResult(kind: "json" | "csv")`
- CSV 构造：`buildCsv(columns, rows)`

### 2.2 后端角色

后端不提供“导出文件”接口。后端只负责执行 SQL 并返回结构化查询结果 JSON：

- 接口：`POST /api/v1/dbs/{name}/query`
  - 文件：`w2/db_query/backend/src/api/v1/query.py`
- 编排执行：`DatabaseOrchestrator.execute_sql`
  - 文件：`w2/db_query/backend/src/application/database_orchestrator.py`
- 结果构建：`QueryService.execute_query`
  - 文件：`w2/db_query/backend/src/services/query_service.py`

结论：导出文件由浏览器端生成并下载，不经过后端二次处理。

## 3. 数据来源与数据模型

导出的源数据来自前端状态 `queryResult`：

- 定义位置：`w2/db_query/frontend/src/types/models.ts` 中 `QueryResult`
- 关键字段：
  - `columns: { name, type }[]`
  - `rows: Record<string, unknown>[]`
  - `rowCount`
  - `executionTime`
  - `query`

在执行查询时，前端通过 `apiClient.executeQuery(...)` 拿到结果并设置到 `queryResult`：

- 文件：`w2/db_query/frontend/src/App.tsx`
- 流程：
  1. 点击 `EXECUTE`
  2. 调用 `apiClient.executeQuery(selectedDbName, { sql })`
  3. 成功后 `setQueryResult(result)`
  4. 失败则 `setQueryResult(null)` 并显示错误

因此导出行为依赖“最近一次成功查询结果”。

## 4. UI 交互与触发条件

`RESULTS` 卡片中提供两个按钮：

- `EXPORT CSV`
- `EXPORT JSON`

触发规则：

- 当 `queryResult` 不存在时，按钮 `disabled`
- 当 `queryResult` 存在时，按钮可点击

这意味着：

- 还没执行成功查询时，无法导出
- 查询失败后（`queryResult` 被清空）也无法导出

## 5. 导出处理主流程（exportResult）

`exportResult(kind)` 的处理步骤如下：

1. 判断：若 `queryResult` 为空，直接返回。
2. 根据 `kind` 生成内容字符串：
   - `json`：`JSON.stringify(queryResult.rows, null, 2)`
   - `csv`：`buildCsv(queryResult.columns.map(c => c.name), queryResult.rows)`
3. 创建 `Blob`：
   - JSON: `application/json`
   - CSV: `text/csv`
4. 动态创建 `<a>` 元素并设置下载地址：
   - `href = URL.createObjectURL(blob)`
   - `download = query-result.{kind}`
5. 调用 `link.click()` 触发浏览器下载。
6. 调用 `URL.revokeObjectURL(link.href)` 释放对象 URL。

核心特征：

- 全程浏览器原生 API 实现（`Blob + object URL + a.click()`）
- 无额外三方导出库
- 文件名固定为 `query-result.csv` / `query-result.json`

## 6. CSV 生成规则（buildCsv）

`buildCsv(columns, rows)` 的策略：

1. 表头：
   - 直接使用 `columns.join(",")`
2. 数据行：
   - 按 `columns` 顺序取每一列对应值，保证列顺序稳定
   - 值转换规则：
     - `null` / `undefined` -> 空字符串
     - 其他值 -> `String(rawValue)`
3. 转义规则：
   - 当字段值包含以下任意字符时，使用双引号包裹：
     - `,`
     - `"`
     - `\n`
   - 字段内双引号替换为 `""`（双写）
4. 最终输出：
   - `[header, ...values].join("\n")`

说明：这是一个轻量 CSV 序列化实现，已覆盖基础逗号、引号、换行场景。

## 7. JSON 生成规则

JSON 导出直接序列化 `queryResult.rows`：

- 使用 `JSON.stringify(rows, null, 2)`，带 2 空格缩进
- 不包含 `columns / rowCount / executionTime / query` 元信息
- 输出本质是“结果行对象数组”

## 8. 与结果展示逻辑的一致性

页面表格展示与导出使用同一份 `queryResult` 数据：

- 展示列来自 `queryResult.columns`
- 展示行来自 `queryResult.rows`
- CSV 导出列顺序同样来自 `queryResult.columns`
- JSON 导出使用 `queryResult.rows`

因此，导出内容与当前页面已加载结果保持一致，不额外请求后端。

## 9. 当前实现边界

当前代码中的明确边界如下：

- 没有后端导出接口（仅前端本地导出）
- 没有导出进度、导出成功提示、失败提示
- 没有自定义文件名、编码、分隔符等配置
- 没有针对超大结果集的分块/流式导出
- JSON 导出不带查询元信息，仅导出 `rows`
