# pg-mcp 代码评审报告（针对 0002 设计稿与 0004 实施计划）

> 评审范围：`w5/pg-mcp`  
> 对照文档：`specs/w5/0002-pg-mcp-design.md`、`specs/w5/0004-pg-mcp-impl-plan.md`  
> 评审时间：2026-02-26

## 评审方法

- 已按 `requesting-code-review` skill 流程发起 review。
- 实际执行 `codex exec review --uncommitted` 两次，均超时，未产出可用文本结果（临时文件为空）。
- 因此采用“规范逐项核对 + 代码静态审查 + 本地测试”完成本次评审。

---

## Findings（按严重级别）

### High

1. 通用异常响应暴露内部错误细节，和实施计划“不要暴露内部细节”不一致  
问题：
- 在兜底 `except Exception` 分支中，响应 `details` 直接包含 `str(exc)`。

影响：
- 可能向客户端泄露内部实现细节（数据库/依赖错误文本），与错误处理安全目标冲突。

证据：
- `w5/pg-mcp/pg_mcp/server.py:161`
- `w5/pg-mcp/pg_mcp/server.py:162`
- `specs/w5/0004-pg-mcp-impl-plan.md:684`

建议修复：
- 兜底错误响应中移除原始 `exc` 文本，仅返回通用错误信息和 `request_id`。
- 原始异常细节只记录在服务端结构化日志中（受控可检索）。

### Medium

1. `enable_prompt_injection_check` 配置项已定义但未落地到执行链路  
问题：
- 设计稿包含该安全开关，但当前调用路径未看到对应检测逻辑。

影响：
- 配置项形同虚设，安全能力与设计约定存在偏差；运维侧可能误判已启用防护。

证据：
- `w5/pg-mcp/pg_mcp/config/settings.py:147`
- `w5/pg-mcp/pg_mcp/server.py:91`（当前只进入 SQLValidator 流程）
- `specs/w5/0002-pg-mcp-design.md:178`
- `specs/w5/0002-pg-mcp-design.md:1555`

建议修复：
- 在 `query_database` 链路中增加输入风险检测步骤，并受 `enable_prompt_injection_check` 控制。
- 为开启/关闭两种模式增加单元测试。

2. 通用异常文案与设计/实施计划中的约定文案不一致  
问题：
- 设计/计划里示例文案为“查询执行过程中发生错误，请稍后重试”，当前实现为英文文案。

影响：
- 对外错误契约不稳定，不利于上层统一错误处理与文案国际化策略。

证据：
- `w5/pg-mcp/pg_mcp/server.py:161`
- `specs/w5/0002-pg-mcp-design.md:438`
- `specs/w5/0004-pg-mcp-impl-plan.md:684`

建议修复：
- 统一错误文案策略：要么回归规范文案，要么在规范中更新为当前策略并声明 i18n 规则。

### Low

1. 降级路径测试仍偏“单元模拟”，缺少更真实的集成验证  
问题：
- 已有降级逻辑（健康/不健康库），但测试主要依赖 mock，未覆盖“多库部分失败”的真实集成场景。

影响：
- 线上边界行为（尤其连接抖动和部分库失败）可验证性仍不够强。

证据：
- `w5/pg-mcp/tests/test_lifespan.py:28`
- `w5/pg-mcp/tests/test_lifespan.py:63`
- `w5/pg-mcp/tests/integration/test_e2e.py:37`（当前集成用例单库）

建议修复：
- 增加多库集成用例（至少 1 个健康 + 1 个失败）验证启动降级与请求行为。

---

## 符合项（有证据）

1. `query_database` Tool 主流程存在且符合设计主链路  
证据：
- `w5/pg-mcp/pg_mcp/server.py:34`
- `specs/w5/0002-pg-mcp-design.md:346`
- `specs/w5/0004-pg-mcp-impl-plan.md:655`

2. SQL 安全校验（白名单 + 危险函数拦截）已实现  
证据：
- `w5/pg-mcp/pg_mcp/security/validator.py:51`
- `w5/pg-mcp/pg_mcp/security/validator.py:75`
- `specs/w5/0002-pg-mcp-design.md:450`
- `specs/w5/0004-pg-mcp-impl-plan.md:249`

3. LLM 调用重试与指数退避已实现，且有测试  
证据：
- `w5/pg-mcp/pg_mcp/services/llm.py:74`
- `w5/pg-mcp/pg_mcp/services/llm.py:151`
- `w5/pg-mcp/tests/test_llm.py:89`
- `w5/pg-mcp/tests/test_llm.py:112`
- `specs/w5/0004-pg-mcp-impl-plan.md:503`

4. LIMIT 防护与截断处理已实现  
证据：
- `w5/pg-mcp/pg_mcp/services/executor.py:155`
- `w5/pg-mcp/pg_mcp/services/executor.py:127`
- `w5/pg-mcp/tests/test_executor.py:30`
- `w5/pg-mcp/tests/test_executor.py:152`

5. 多数据库配置、默认库选择机制存在  
证据：
- `w5/pg-mcp/pg_mcp/config/settings.py:161`
- `w5/pg-mcp/pg_mcp/config/settings.py:178`
- `w5/pg-mcp/pg_mcp/server.py:68`
- `specs/w5/0004-pg-mcp-impl-plan.md:874`

6. 本轮整改新增能力与质量状态  
证据：
- 结构化日志与 request_id 全链路：`w5/pg-mcp/pg_mcp/utils/logging.py:13`、`w5/pg-mcp/pg_mcp/server.py:42`
- 数据库连接重试/降级：`w5/pg-mcp/pg_mcp/services/executor.py:203`、`w5/pg-mcp/pg_mcp/__main__.py:35`
- 限流：`w5/pg-mcp/pg_mcp/services/rate_limiter.py:12`、`w5/pg-mcp/pg_mcp/server.py:78`
- 限流测试：`w5/pg-mcp/tests/test_rate_limiter.py:11`

---

## 测试结果

- `uv run ruff check .`：通过
- `uv run python -m pytest -q`：`88 passed, 5 skipped`

说明：
- 跳过项为集成测试开关控制的用例，非本轮回归失败。

---

## 结论

- 相对 `0002` 与 `0004`，当前实现主干能力基本对齐，且本轮已补齐可观测性最小闭环、数据库重试/降级、限流与测试矩阵。
- 仍有 1 个 High + 2 个 Medium + 1 个 Low 级问题，建议在合并前至少处理 High 与 Medium 项。
