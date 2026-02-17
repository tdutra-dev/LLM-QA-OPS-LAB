// packages/sim/src/eventBus.ts
import type { RuntimeEvent } from "./events";

export type EventHandler = (e: RuntimeEvent) => void;

export class RuntimeEventBus {
  private handlers: EventHandler[] = [];

  on(handler: EventHandler) {
    this.handlers.push(handler);
    return () => {
      this.handlers = this.handlers.filter(h => h !== handler);
    };
  }

  emit(e: RuntimeEvent) {
    for (const h of this.handlers) h(e);
  }
}
