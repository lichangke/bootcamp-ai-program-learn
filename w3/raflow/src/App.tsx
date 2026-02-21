import { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { OverlayWindow } from "./components/OverlayWindow";
import { SettingsPanel, type SettingsDraft } from "./components/SettingsPanel";
import "./App.css";

type BackendStatus = {
  service: string;
  version: string;
  ready: boolean;
};

type PermissionState = "granted" | "denied" | "unknown";

type PermissionReport = {
  microphone: PermissionState;
  accessibility: PermissionState;
  guidance: string[];
};

type MetricSummary = {
  samples: number;
  averageMs: number;
  p95Ms: number;
  maxMs: number;
};

type PerformanceReport = {
  generatedAtMs: number;
  audioProcessing: MetricSummary;
  networkSend: MetricSummary;
  injection: MetricSummary;
  endToEnd: MetricSummary;
  droppedAudioChunks: number;
  droppedCommittedTranscripts: number;
  sentAudioChunks: number;
  sentAudioBatches: number;
  warnings: string[];
};

type AppSettings = SettingsDraft;

type EdgeStateKind = "auth" | "network" | "permission" | "empty" | "generic";

type EdgeState = {
  kind: EdgeStateKind;
  title: string;
  detail: string;
  recoverHint: string;
};

const DEFAULT_SETTINGS: AppSettings = {
  apiKey: "",
  languageCode: "eng",
  hotkey: "Ctrl+N",
  injectionThreshold: 10,
  partialRewriteEnabled: true,
  partialRewriteMaxBackspace: 12,
  partialRewriteWindowMs: 140,
};

function classifyError(message: string): EdgeState {
  const normalized = message.toLowerCase();
  if (
    normalized.includes("api key") ||
    normalized.includes("authentication") ||
    normalized.includes("auth")
  ) {
    return {
      kind: "auth",
      title: "Authentication Failed",
      detail: message,
      recoverHint: "Check API key validity in Settings, then save again.",
    };
  }

  if (
    normalized.includes("network") ||
    normalized.includes("websocket") ||
    normalized.includes("connection") ||
    normalized.includes("transport")
  ) {
    return {
      kind: "network",
      title: "Network Unavailable",
      detail: message,
      recoverHint: "Check connectivity and retry start recording.",
    };
  }

  if (
    normalized.includes("permission") ||
    normalized.includes("accessibility") ||
    normalized.includes("denied") ||
    normalized.includes("not authorized")
  ) {
    return {
      kind: "permission",
      title: "Permission Missing",
      detail: message,
      recoverHint: "Grant microphone/accessibility permissions in OS settings.",
    };
  }

  return {
    kind: "generic",
    title: "Runtime Error",
    detail: message,
    recoverHint: "Retry the action. If it persists, inspect logs.",
  };
}

function emptyTranscriptState(): EdgeState {
  return {
    kind: "empty",
    title: "Empty Transcript",
    detail: "A committed transcript arrived without text content.",
    recoverHint: "Speak clearly and keep recording slightly longer.",
  };
}

function App() {
  const [status, setStatus] = useState<BackendStatus | null>(null);
  const [recordingError, setRecordingError] = useState<string>("");
  const [settingsError, setSettingsError] = useState<string>("");
  const [edgeState, setEdgeState] = useState<EdgeState | null>(null);
  const [partialTranscript, setPartialTranscript] = useState<string>("");
  const [committedTranscript, setCommittedTranscript] = useState<string>("");
  const [recordingState, setRecordingState] = useState<string>("Idle");
  const [overlayVisible, setOverlayVisible] = useState<boolean>(true);
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [saveMessage, setSaveMessage] = useState<string>("");
  const [isSavingSettings, setIsSavingSettings] = useState<boolean>(false);
  const [permissions, setPermissions] = useState<PermissionReport | null>(null);
  const [performance, setPerformance] = useState<PerformanceReport | null>(null);

  const applyRecordingError = useCallback((message: string) => {
    const trimmed = message.trim();
    if (!trimmed) {
      return;
    }
    setRecordingError(trimmed);
    setEdgeState(classifyError(trimmed));
  }, []);

  const clearTransientError = useCallback(() => {
    setRecordingError("");
    setEdgeState((current) => (current?.kind === "empty" ? current : null));
  }, []);

  const refreshStatus = useCallback(async () => {
    try {
      clearTransientError();
      const nextStatus = await invoke<BackendStatus>("app_status");
      setStatus(nextStatus);
    } catch (invokeError) {
      applyRecordingError(String(invokeError));
    }
  }, [applyRecordingError, clearTransientError]);

  const refreshPermissions = useCallback(async () => {
    try {
      const report = await invoke<PermissionReport>("check_permissions");
      setPermissions(report);
      if (report.microphone === "denied" || report.accessibility === "denied") {
        setEdgeState({
          kind: "permission",
          title: "Permission Missing",
          detail: report.guidance.join(" "),
          recoverHint: "Open OS settings and grant required permissions.",
        });
      }
    } catch (invokeError) {
      applyRecordingError(String(invokeError));
    }
  }, [applyRecordingError]);

  const refreshPerformance = useCallback(async () => {
    try {
      const report = await invoke<PerformanceReport>("get_performance_report");
      setPerformance(report);
    } catch (invokeError) {
      applyRecordingError(String(invokeError));
    }
  }, [applyRecordingError]);

  const loadSettings = useCallback(async () => {
    try {
      const loaded = await invoke<AppSettings>("get_settings");
      setSettings(loaded);
      setSettingsError("");
    } catch (invokeError) {
      applyRecordingError(String(invokeError));
    }
  }, [applyRecordingError]);

  const saveSettings = useCallback(async () => {
    setIsSavingSettings(true);
    setSettingsError("");
    setSaveMessage("");
    try {
      const saved = await invoke<AppSettings>("save_settings", { settings });
      setSettings(saved);
      setSaveMessage("Settings saved and applied.");
      clearTransientError();
    } catch (invokeError) {
      const message = String(invokeError);
      setSettingsError(message);
      setEdgeState(classifyError(message));
    } finally {
      setIsSavingSettings(false);
    }
  }, [clearTransientError, settings]);

  const startRecording = useCallback(async () => {
    try {
      clearTransientError();
      await invoke("start_recording");
    } catch (invokeError) {
      applyRecordingError(String(invokeError));
    }
  }, [applyRecordingError, clearTransientError]);

  const stopRecording = useCallback(async () => {
    try {
      clearTransientError();
      await invoke("stop_recording");
      await refreshPerformance();
    } catch (invokeError) {
      applyRecordingError(String(invokeError));
    }
  }, [applyRecordingError, clearTransientError, refreshPerformance]);

  useEffect(() => {
    void refreshStatus();
    void loadSettings();
    void refreshPermissions();
    void refreshPerformance();
  }, [loadSettings, refreshPermissions, refreshPerformance, refreshStatus]);

  useEffect(() => {
    const listeners = [
      listen<string>("partial_transcript", (event) => {
        setPartialTranscript(event.payload);
      }),
      listen<string>("committed_transcript", (event) => {
        const text = event.payload;
        setCommittedTranscript(text);
        if (!text.trim()) {
          setEdgeState(emptyTranscriptState());
          return;
        }
        setEdgeState((current) => (current?.kind === "empty" ? null : current));
      }),
      listen<string>("recording_state", (event) => {
        setRecordingState(event.payload);
        if (event.payload !== "Error") {
          clearTransientError();
        }
      }),
      listen<string>("recording_error", (event) => {
        applyRecordingError(event.payload);
      }),
      listen<string>("session_started", () => {
        setRecordingState("Listening");
        clearTransientError();
      }),
      listen<boolean>("overlay_visibility_changed", (event) => {
        setOverlayVisible(event.payload);
      }),
    ];

    return () => {
      for (const listener of listeners) {
        void listener.then((unlisten) => unlisten());
      }
    };
  }, [applyRecordingError, clearTransientError]);

  return (
    <main className="app-shell">
      <header className="hero">
        <h1>RAFlow Desktop Console</h1>
        <p>Configure speech transcription, control recording, and monitor realtime states.</p>
      </header>

      <section className="card control-card">
        <h2>Runtime Control</h2>
        <div className="row">
          <button type="button" onClick={() => void refreshStatus()}>
            Refresh
          </button>
          <button type="button" onClick={() => void refreshPermissions()}>
            Check Permissions
          </button>
          <button type="button" onClick={() => void refreshPerformance()}>
            Refresh Metrics
          </button>
          <button type="button" onClick={() => void startRecording()}>
            Start
          </button>
          <button type="button" onClick={() => void stopRecording()}>
            Stop + Flush
          </button>
        </div>
        <div className="runtime-meta">
          <p>
            <strong>Backend:</strong>{" "}
            {status
              ? `${status.service} ${status.version} (${status.ready ? "ready" : "not ready"})`
              : "loading..."}
          </p>
          <p>
            <strong>State:</strong> <span className="state-inline">{recordingState}</span>
          </p>
        </div>
        {recordingError ? <p className="error">Error: {recordingError}</p> : null}
      </section>

      {permissions ? (
        <section className="card">
          <h2>Permission Health</h2>
          <p>
            <strong>Microphone:</strong>{" "}
            <span className={`perm perm-${permissions.microphone}`}>{permissions.microphone}</span>
          </p>
          <p>
            <strong>Accessibility:</strong>{" "}
            <span className={`perm perm-${permissions.accessibility}`}>{permissions.accessibility}</span>
          </p>
          <p>{permissions.guidance.join(" ")}</p>
        </section>
      ) : null}

      {performance ? (
        <section className="card">
          <h2>Performance Report</h2>
          <div className="perf-grid">
            <p>
              <strong>Audio Processing P95:</strong> {performance.audioProcessing.p95Ms}ms
            </p>
            <p>
              <strong>Network Send P95:</strong> {performance.networkSend.p95Ms}ms
            </p>
            <p>
              <strong>Injection P95:</strong> {performance.injection.p95Ms}ms
            </p>
            <p>
              <strong>End-to-End P95:</strong> {performance.endToEnd.p95Ms}ms
            </p>
          </div>
          <p>
            <strong>Sent:</strong> {performance.sentAudioChunks} chunks in {performance.sentAudioBatches} batches
          </p>
          <p>
            <strong>Dropped:</strong> audio {performance.droppedAudioChunks}, committed{" "}
            {performance.droppedCommittedTranscripts}
          </p>
          {performance.warnings.length > 0 ? (
            <p className="error">{performance.warnings.join(" ")}</p>
          ) : (
            <p>All tracked metrics are within expected range.</p>
          )}
        </section>
      ) : null}

      {edgeState ? (
        <section className={`card edge-card edge-${edgeState.kind}`}>
          <h2>{edgeState.title}</h2>
          <p>{edgeState.detail}</p>
          <p className="edge-hint">{edgeState.recoverHint}</p>
        </section>
      ) : null}

      {overlayVisible ? (
        <OverlayWindow
          stateLabel={recordingState}
          partialTranscript={partialTranscript}
          committedTranscript={committedTranscript}
          errorMessage={recordingError}
        />
      ) : (
        <section className="card overlay-hidden">
          <h2>Overlay Hidden</h2>
          <p>Use tray menu action "Show/Hide Overlay" to display realtime transcript preview.</p>
        </section>
      )}

      <SettingsPanel
        settings={settings}
        onApiKeyChange={(value) => {
          setSettings((current) => ({ ...current, apiKey: value }));
          setSettingsError("");
          setSaveMessage("");
        }}
        onLanguageChange={(value) => {
          setSettings((current) => ({ ...current, languageCode: value }));
          setSettingsError("");
          setSaveMessage("");
        }}
        onHotkeyChange={(value) => {
          setSettings((current) => ({ ...current, hotkey: value }));
          setSettingsError("");
          setSaveMessage("");
        }}
        onInjectionThresholdChange={(value) => {
          if (!Number.isFinite(value)) {
            return;
          }
          const normalized = Math.max(1, Math.min(1024, Math.trunc(value)));
          setSettings((current) => ({ ...current, injectionThreshold: normalized }));
          setSettingsError("");
          setSaveMessage("");
        }}
        onPartialRewriteEnabledChange={(value) => {
          setSettings((current) => ({ ...current, partialRewriteEnabled: value }));
          setSettingsError("");
          setSaveMessage("");
        }}
        onPartialRewriteMaxBackspaceChange={(value) => {
          if (!Number.isFinite(value)) {
            return;
          }
          const normalized = Math.max(0, Math.min(64, Math.trunc(value)));
          setSettings((current) => ({ ...current, partialRewriteMaxBackspace: normalized }));
          setSettingsError("");
          setSaveMessage("");
        }}
        onPartialRewriteWindowMsChange={(value) => {
          if (!Number.isFinite(value)) {
            return;
          }
          const normalized = Math.max(0, Math.min(2000, Math.trunc(value)));
          setSettings((current) => ({ ...current, partialRewriteWindowMs: normalized }));
          setSettingsError("");
          setSaveMessage("");
        }}
        onSave={() => void saveSettings()}
        isSaving={isSavingSettings}
        saveMessage={saveMessage}
        saveError={settingsError}
      />
    </main>
  );
}

export default App;
