/**
 * OpenClaw — AI Telemetry & Reasoning Hub
 *
 * Composes the three sub-components:
 *  1. StreamConsciousnessTerminal (top — dominant)
 *  2. ConvictionGauges (right sidebar)
 *  3. ExecutionLedger (bottom — full width)
 *
 * Layout: Split-pane with the terminal taking most vertical space.
 */

import StreamConsciousnessTerminal from './StreamConsciousnessTerminal';
import ConvictionGauges from './ConvictionGauges';
import ExecutionLedger from './ExecutionLedger';

export default function AITelemetryHub() {
  return (
    <section className="telemetry-hub" aria-label="AI Telemetry & Reasoning Hub">
      {/* Section Header */}
      <div className="telemetry-hub-header">
        <div className="telemetry-hub-title-row">
          <div className="telemetry-hub-icon">⬡</div>
          <div>
            <h2 className="telemetry-hub-title">AI Telemetry & Reasoning Hub</h2>
            <p className="telemetry-hub-subtitle">
              XAUUSD · Real-time LLM inference stream · OpenClaw Neural Engine
            </p>
          </div>
        </div>
      </div>

      {/* Upper split: Terminal + Gauges */}
      <div className="telemetry-upper-split">
        {/* Left — Stream terminal (dominant) */}
        <div className="telemetry-terminal-pane">
          <StreamConsciousnessTerminal />
        </div>

        {/* Right — Conviction gauges sidebar */}
        <div className="telemetry-gauges-pane">
          <ConvictionGauges />
        </div>
      </div>

      {/* Lower — Execution Ledger (full width) */}
      <div className="telemetry-ledger-pane">
        <ExecutionLedger />
      </div>
    </section>
  );
}
