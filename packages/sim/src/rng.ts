// packages/sim/src/rng.ts

export function mulberry32(seed: number) {
  let a = seed >>> 0;
  return function rand() {
    a |= 0;
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function pickOne<T>(rand: () => number, items: T[]): T {
  return items[Math.floor(rand() * items.length)];
}

export function chance(rand: () => number, p: number): boolean {
  return rand() < p;
}

export function jitter(rand: () => number, baseMs: number, jitterMs: number): number {
  const delta = (rand() * 2 - 1) * jitterMs; // [-jitter, +jitter]
  return Math.max(0, Math.round(baseMs + delta));
}
