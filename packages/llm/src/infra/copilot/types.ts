export type CopilotInput = {
  service: string;
  environment: string;

  healthStatus: "OK" | "WARN" | "CRITICAL";

  kpis: {
    retryRate: number;
    fallbackRate: number;
    avgAttempts: number;
  };

  issues: string[];

  timestamp: number;
};

export type CopilotOutput = {
  summary: string;
  probableCause: string;
  suggestedActions: string[];
  confidence: number; // 0 → 1
};

