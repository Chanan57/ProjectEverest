/**
 * OpenClaw — Stream of Consciousness Terminal
 *
 * Renders streaming LLM tokens with Markdown-aware formatting.
 *
 * Performance Architecture:
 * ─────────────────────────
 * The key problem with streaming text + React: calling setState on every token
 * (potentially 50-100 tokens/sec) would cause a re-render storm, freezing the UI.
 *
 * Solution: We subscribe to the Zustand store OUTSIDE of React state. We use a
 * `useRef` to hold the latest text, and a `requestAnimationFrame` loop to flush
 * updates to the DOM at ~60fps max — decoupling the render rate from the token rate.
 *
 * The markdown parser runs on the accumulated fullText only during the rAF flush,
 * not on every token. This keeps the CPU cost deterministic.
 */

import { useEffect, useRef, useCallback } from 'react';
import { useAITelemetryStore } from '../../store/useAITelemetryStore';

/* ── Lightweight markdown→HTML transformer ─────────────────────────────────── */
function parseMarkdown(raw: string): string {
  return raw
    // Bold: **text** or __text__
    .replace(/\*\*(.*?)\*\*/g, '<strong class="md-bold">$1</strong>')
    .replace(/__(.*?)__/g, '<strong class="md-bold">$1</strong>')
    // Italic: *text* or _text_
    .replace(/\*(.*?)\*/g, '<em class="md-em">$1</em>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code class="md-code">$1</code>')
    // Unordered list items (lines starting with "- " or "• ")
    .replace(/^[•\-]\s+(.+)$/gm, '<li class="md-li">$1</li>')
    // Wrap consecutive <li> in <ul>
    .replace(/(<li[\s\S]*?<\/li>)(\n<li|$)/g, '$1$2')
    // Section headers (lines starting with ##)
    .replace(/^##\s+(.+)$/gm, '<h3 class="md-h3">$1</h3>')
    .replace(/^#\s+(.+)$/gm, '<h2 class="md-h2">$1</h2>')
    // Line breaks — preserve newlines as <br> outside of list items
    .replace(/\n(?!<)/g, '<br/>');
}

/* ── Cursor blink element ───────────────────────────────────────────────────── */
const CURSOR_HTML = '<span class="stream-cursor">▋</span>';

/* ── Component ──────────────────────────────────────────────────────────────── */
export default function StreamConsciousnessTerminal() {
  const contentRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number | null>(null);
  const lastTextRef = useRef<string>('');
  const isUserScrolledRef = useRef(false);

  // Subscribe to the store imperatively — no React re-renders here.
  const getState = useAITelemetryStore.getState;
  const subscribe = useAITelemetryStore.subscribe;

  /* Flush latest text to DOM via rAF — max 60fps regardless of token rate */
  const scheduleFlush = useCallback(() => {
    if (rafRef.current !== null) return; // already queued
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;
      const { fullText, isStreaming } = getState();

      if (!contentRef.current) return;
      if (fullText === lastTextRef.current) return; // nothing changed

      lastTextRef.current = fullText;
      const html = parseMarkdown(fullText) + (isStreaming ? CURSOR_HTML : '');
      contentRef.current.innerHTML = html;

      // Auto-scroll only if user hasn't manually scrolled up
      if (!isUserScrolledRef.current && scrollRef.current) {
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      }
    });
  }, [getState]);

  /* Subscribe to store changes — fires on EVERY state change */
  useEffect(() => {
    const unsub = subscribe(() => scheduleFlush());
    scheduleFlush(); // Initial paint
    return () => {
      unsub();
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [subscribe, scheduleFlush]);

  /* Detect manual scroll to pause auto-scroll */
  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    isUserScrolledRef.current = scrollHeight - scrollTop - clientHeight > 40;
  }, []);

  /* Reactive values for the status bar (these CAN use React state since they're low-freq) */
  const isStreaming = useAITelemetryStore((s) => s.isStreaming);
  const sessionId = useAITelemetryStore((s) => s.session?.id ?? null);

  return (
    <div className="terminal-shell">
      {/* ── Header bar ─────────────────────────────────────────────── */}
      <div className="terminal-header">
        <div className="terminal-header-left">
          <div className={`terminal-status-dot ${isStreaming ? 'dot-streaming' : 'dot-idle'}`} />
          <span className="terminal-label">STREAM OF CONSCIOUSNESS</span>
          {sessionId && (
            <span className="terminal-session-id">SID:{sessionId.slice(0, 8)}</span>
          )}
        </div>
        <div className="terminal-header-right">
          <span className="terminal-badge">
            {isStreaming ? '⟳ LIVE INFERENCE' : '◉ STANDBY'}
          </span>
        </div>
      </div>

      {/* ── Main scroll area ────────────────────────────────────────── */}
      <div
        ref={scrollRef}
        className="terminal-scroll-area"
        onScroll={handleScroll}
      >
        {/* Prompt prefix */}
        <div className="terminal-prompt-row">
          <span className="terminal-prompt-symbol">⬡</span>
          <span className="terminal-prompt-label">OpenClaw AI · XAUUSD Reasoning Engine</span>
        </div>

        {/* Content — mutated directly by rAF for zero-React-render performance */}
        <div
          ref={contentRef}
          className="terminal-content"
          aria-live="polite"
          aria-label="AI reasoning stream"
        />

        {/* Empty state */}
        {!isStreaming && lastTextRef.current === '' && (
          <div className="terminal-empty-state">
            <div className="terminal-empty-icon">◈</div>
            <p>Awaiting AI inference signal…</p>
            <p className="terminal-empty-sub">
              The reasoning engine will stream analysis here in real-time.
            </p>
          </div>
        )}
      </div>

      {/* ── Footer scan line ────────────────────────────────────────── */}
      {isStreaming && <div className="terminal-scanline" />}
    </div>
  );
}
