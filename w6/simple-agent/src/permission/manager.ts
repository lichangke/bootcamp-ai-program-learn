import type { Session } from "../session/session.ts";

export type PermissionAction = "allow" | "deny" | "ask";

export interface Permission {
  tool: string;
  action: PermissionAction;
  patterns?: string[];
}

export interface PermissionContext {
  tool: string;
  args: unknown;
  session: Session;
}

export type AskUserHandler = (ctx: PermissionContext) => Promise<"allow" | "deny">;

export class PermissionManager {
  private rules: Permission[] = [];
  private readonly askUserHandler: AskUserHandler | undefined;

  constructor(rules: Permission[] = [], askUserHandler?: AskUserHandler) {
    this.rules = [...rules];
    this.askUserHandler = askUserHandler;
  }

  setRules(rules: Permission[]): void {
    this.rules = [...rules];
  }

  addRule(rule: Permission): void {
    this.rules.push(rule);
  }

  listRules(): Permission[] {
    return [...this.rules];
  }

  async check(ctx: PermissionContext): Promise<"allow" | "deny"> {
    for (const rule of this.rules) {
      if (!this.matchesRule(rule, ctx)) {
        continue;
      }

      if (rule.action === "ask") {
        return this.askUser(ctx);
      }

      return rule.action;
    }

    return "deny";
  }

  private async askUser(ctx: PermissionContext): Promise<"allow" | "deny"> {
    if (!this.askUserHandler) {
      return "deny";
    }
    return this.askUserHandler(ctx);
  }

  private matchesRule(rule: Permission, ctx: PermissionContext): boolean {
    if (!this.matchWildcard(rule.tool, ctx.tool)) {
      return false;
    }

    if (!rule.patterns || rule.patterns.length === 0) {
      return true;
    }

    const payload = this.stringifyArgs(ctx.args);
    return rule.patterns.some((pattern) => this.matchWildcard(pattern, payload));
  }

  private matchWildcard(pattern: string, value: string): boolean {
    if (pattern === "*") {
      return true;
    }

    const escaped = pattern
      .replace(/[.+?^${}()|[\]\\]/g, "\\$&")
      .replaceAll("*", ".*");
    return new RegExp(`^${escaped}$`, "u").test(value);
  }

  private stringifyArgs(args: unknown): string {
    try {
      return JSON.stringify(args) ?? "";
    } catch {
      return String(args);
    }
  }
}
