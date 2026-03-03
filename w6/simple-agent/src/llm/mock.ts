import type { LLMClient, LLMEvent, LLMInput, LLMOutput } from "./client.ts";

export interface MockLLMStep {
  output?: LLMOutput;
  streamEvents?: LLMEvent[];
}

export class ScriptedLLMClient implements LLMClient {
  private cursor = 0;
  private readonly steps: MockLLMStep[];

  constructor(steps: MockLLMStep[]) {
    this.steps = steps;
  }

  async generate(_input: LLMInput): Promise<LLMOutput> {
    const step = this.nextStep();
    if (!step.output) {
      throw new Error("Mock step missing generate output.");
    }
    return step.output;
  }

  async *stream(_input: LLMInput): AsyncGenerator<LLMEvent> {
    const step = this.nextStep();
    if (!step.streamEvents) {
      throw new Error("Mock step missing stream events.");
    }

    for (const event of step.streamEvents) {
      yield event;
    }
  }

  private nextStep(): MockLLMStep {
    const step = this.steps[this.cursor];
    this.cursor += 1;
    if (!step) {
      throw new Error(`No scripted LLM step at index ${this.cursor - 1}.`);
    }
    return step;
  }
}
