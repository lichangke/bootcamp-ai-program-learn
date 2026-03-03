import type { PermissionManager } from "../permission/manager.ts";
import { toolResultContent, type ToolCallContent, type ToolResultContent } from "../session/message.ts";
import type { Session } from "../session/session.ts";
import type { ExecutionContext } from "./context.ts";
import type { ToolRegistry } from "./registry.ts";

export class ToolExecutor {
  private readonly registry: ToolRegistry;
  private readonly permissionManager: PermissionManager | undefined;

  constructor(
    registry: ToolRegistry,
    permissionManager?: PermissionManager,
  ) {
    this.registry = registry;
    this.permissionManager = permissionManager;
  }

  async execute(call: ToolCallContent, ctx: ExecutionContext, session?: Session): Promise<ToolResultContent> {
    const tool = this.registry.get(call.name);
    if (!tool) {
      return toolResultContent(call.id, `Tool not found: ${call.name}`, true);
    }

    if (this.permissionManager && session) {
      const decision = await this.permissionManager.check({
        tool: call.name,
        args: call.arguments,
        session,
      });
      if (decision === "deny") {
        return toolResultContent(call.id, `Permission denied for tool: ${call.name}`, true);
      }
    }

    try {
      const result = await tool.execute(call.arguments, ctx);
      const isError = result.error ? true : undefined;
      return toolResultContent(call.id, result.output, isError);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return toolResultContent(call.id, message, true);
    }
  }
}
