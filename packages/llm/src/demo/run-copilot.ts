import { AlertEngine } from "../infra/alerting/AlertEngine.js";

const notifier = {
  notify(event: any) {
    console.log("🚨 ALERT FIRED:", event.name);
  },
};

const engine = new AlertEngine(notifier);

await engine.evaluateHealth({
  status: "CRITICAL",
  issues: ["timeout spike"],
  kpis: {
    retryRate: 0.5,
    fallbackRate: 0.2,
    avgAttempts: 2.4,
  },
});
