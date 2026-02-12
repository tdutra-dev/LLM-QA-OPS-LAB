export class ConsoleNotifier {
    notify(event) {
        const icon = event.severity === "critical" ? "🚨" : event.severity === "warn" ? "⚠️" : "ℹ️";
        console.log(`\n${icon} ALERT: ${event.name}\n- severity: ${event.severity}\n- message: ${event.message}\n- time: ${new Date(event.timestamp).toISOString()}`);
        if (event.context && Object.keys(event.context).length > 0) {
            console.log("- context:", JSON.stringify(event.context, null, 2));
        }
    }
}
//# sourceMappingURL=notifiers.js.map