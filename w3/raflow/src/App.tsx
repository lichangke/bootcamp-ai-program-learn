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
type UiLocale = "en" | "zh";

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

const UI_LOCALE_STORAGE_KEY = "raflow.ui.locale";

const UI_COPY = {
  en: {
    heroTitle: "RAFlow Desktop Console",
    heroSubtitle: "Configure speech transcription, control recording, and monitor realtime states.",
    uiLanguageLabel: "Interface Language",
    uiLanguageZh: "Chinese",
    uiLanguageEn: "English",
    runtimeControl: "Runtime Control",
    refresh: "Refresh",
    checkPermissions: "Check Permissions",
    refreshMetrics: "Refresh Metrics",
    start: "Start",
    stopAndFlush: "Stop + Flush",
    backend: "Backend",
    ready: "ready",
    notReady: "not ready",
    loading: "loading...",
    state: "State",
    errorPrefix: "Error",
    permissionHealth: "Permission Health",
    microphone: "Microphone",
    accessibility: "Accessibility",
    performanceReport: "Performance Report",
    audioP95: "Audio Processing P95",
    networkP95: "Network Send P95",
    injectionP95: "Injection P95",
    endToEndP95: "End-to-End P95",
    sent: "Sent",
    dropped: "Dropped",
    audio: "audio",
    committed: "committed",
    allTrackedGood: "All tracked metrics are within expected range.",
    overlayHidden: "Overlay Hidden",
    overlayHiddenHint: 'Use tray menu action "Show/Hide Overlay" to display realtime transcript preview.',
    settingsSaved: "Settings saved and applied.",
    permissionMissingTitle: "Permission Missing",
    permissionMissingHint: "Open OS settings and grant required permissions.",
    permissionGranted: "granted",
    permissionDenied: "denied",
    permissionUnknown: "unknown",
    authTitle: "Authentication Failed",
    authHint: "Check API key validity in Settings, then save again.",
    networkTitle: "Network Unavailable",
    networkHint: "Check connectivity and retry start recording.",
    permissionTitle: "Permission Missing",
    permissionHint: "Grant microphone/accessibility permissions in OS settings.",
    genericTitle: "Runtime Error",
    genericHint: "Retry the action. If it persists, inspect logs.",
    emptyTitle: "Empty Transcript",
    emptyDetail: "A committed transcript arrived without text content.",
    emptyHint: "Speak clearly and keep recording slightly longer.",
  },
  zh: {
    heroTitle: "RAFlow 桌面控制台",
    heroSubtitle: "配置语音转写、控制录制流程并监控实时状态。",
    uiLanguageLabel: "界面语言",
    uiLanguageZh: "中文",
    uiLanguageEn: "English",
    runtimeControl: "运行控制",
    refresh: "刷新",
    checkPermissions: "检查权限",
    refreshMetrics: "刷新指标",
    start: "开始",
    stopAndFlush: "停止并刷新",
    backend: "后端",
    ready: "就绪",
    notReady: "未就绪",
    loading: "加载中...",
    state: "状态",
    errorPrefix: "错误",
    permissionHealth: "权限健康",
    microphone: "麦克风",
    accessibility: "辅助功能",
    performanceReport: "性能报告",
    audioP95: "音频处理 P95",
    networkP95: "网络发送 P95",
    injectionP95: "注入 P95",
    endToEndP95: "端到端 P95",
    sent: "已发送",
    dropped: "丢弃",
    audio: "音频",
    committed: "已确认文本",
    allTrackedGood: "所有指标均在预期范围内。",
    overlayHidden: "悬浮窗已隐藏",
    overlayHiddenHint: '可通过托盘菜单的“Show/Hide Overlay”重新显示实时预览。',
    settingsSaved: "设置已保存并生效。",
    permissionMissingTitle: "权限缺失",
    permissionMissingHint: "请在系统设置中授予所需权限。",
    permissionGranted: "已授权",
    permissionDenied: "已拒绝",
    permissionUnknown: "未知",
    authTitle: "鉴权失败",
    authHint: "请在设置中检查 API Key 并重新保存。",
    networkTitle: "网络不可用",
    networkHint: "请检查网络连接后重试开始录制。",
    permissionTitle: "权限缺失",
    permissionHint: "请在系统中授予麦克风和辅助功能权限。",
    genericTitle: "运行时错误",
    genericHint: "请重试；若仍失败，请检查日志。",
    emptyTitle: "空转写",
    emptyDetail: "收到了 committed_transcript，但文本为空。",
    emptyHint: "请更清晰说话并稍微延长录制时间。",
  },
} as const;

function detectInitialLocale(): UiLocale {
  if (typeof window === "undefined") {
    return "en";
  }

  const stored = window.localStorage.getItem(UI_LOCALE_STORAGE_KEY);
  if (stored === "zh" || stored === "en") {
    return stored;
  }

  return window.navigator.language.toLowerCase().startsWith("zh") ? "zh" : "en";
}

function classifyError(message: string, locale: UiLocale): EdgeState {
  const copy = UI_COPY[locale];
  const normalized = message.toLowerCase();
  if (
    normalized.includes("api key") ||
    normalized.includes("authentication") ||
    normalized.includes("auth")
  ) {
    return {
      kind: "auth",
      title: copy.authTitle,
      detail: message,
      recoverHint: copy.authHint,
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
      title: copy.networkTitle,
      detail: message,
      recoverHint: copy.networkHint,
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
      title: copy.permissionTitle,
      detail: message,
      recoverHint: copy.permissionHint,
    };
  }

  return {
    kind: "generic",
    title: copy.genericTitle,
    detail: message,
    recoverHint: copy.genericHint,
  };
}

function emptyTranscriptState(locale: UiLocale): EdgeState {
  const copy = UI_COPY[locale];
  return {
    kind: "empty",
    title: copy.emptyTitle,
    detail: copy.emptyDetail,
    recoverHint: copy.emptyHint,
  };
}

function translateRecordingState(stateLabel: string, locale: UiLocale): string {
  if (locale === "en") {
    return stateLabel;
  }

  switch (stateLabel) {
    case "Connecting":
      return "连接中";
    case "Listening":
      return "监听中";
    case "Recording":
      return "录制中";
    case "Processing":
      return "处理中";
    case "Injecting":
      return "注入中";
    case "Error":
      return "错误";
    default:
      return "空闲";
  }
}

function translatePermissionState(state: PermissionState, locale: UiLocale): string {
  const copy = UI_COPY[locale];
  switch (state) {
    case "granted":
      return copy.permissionGranted;
    case "denied":
      return copy.permissionDenied;
    default:
      return copy.permissionUnknown;
  }
}

function App() {
  const [uiLocale, setUiLocale] = useState<UiLocale>(() => detectInitialLocale());
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
  const copy = UI_COPY[uiLocale];

  const applyRecordingError = useCallback((message: string) => {
    const trimmed = message.trim();
    if (!trimmed) {
      return;
    }
    setRecordingError(trimmed);
    setEdgeState(classifyError(trimmed, uiLocale));
  }, [uiLocale]);

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
          title: copy.permissionMissingTitle,
          detail: report.guidance.join(" "),
          recoverHint: copy.permissionMissingHint,
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
      setSaveMessage(copy.settingsSaved);
      clearTransientError();
    } catch (invokeError) {
      const message = String(invokeError);
      setSettingsError(message);
      setEdgeState(classifyError(message, uiLocale));
    } finally {
      setIsSavingSettings(false);
    }
  }, [clearTransientError, copy.settingsSaved, settings, uiLocale]);

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
    if (typeof window !== "undefined") {
      window.localStorage.setItem(UI_LOCALE_STORAGE_KEY, uiLocale);
    }
  }, [uiLocale]);

  useEffect(() => {
    const listeners = [
      listen<string>("partial_transcript", (event) => {
        setPartialTranscript(event.payload);
      }),
      listen<string>("committed_transcript", (event) => {
        const text = event.payload;
        setCommittedTranscript(text);
        if (!text.trim()) {
          setEdgeState(emptyTranscriptState(uiLocale));
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
  }, [applyRecordingError, clearTransientError, uiLocale]);

  return (
    <main className="app-shell">
      <header className="hero">
        <h1>{copy.heroTitle}</h1>
        <p>{copy.heroSubtitle}</p>
        <div className="row locale-switch">
          <span className="locale-label">{copy.uiLanguageLabel}</span>
          <button
            type="button"
            className={uiLocale === "zh" ? "locale-btn active" : "locale-btn"}
            onClick={() => setUiLocale("zh")}
          >
            {copy.uiLanguageZh}
          </button>
          <button
            type="button"
            className={uiLocale === "en" ? "locale-btn active" : "locale-btn"}
            onClick={() => setUiLocale("en")}
          >
            {copy.uiLanguageEn}
          </button>
        </div>
      </header>

      <section className="card control-card">
        <h2>{copy.runtimeControl}</h2>
        <div className="row">
          <button type="button" onClick={() => void refreshStatus()}>
            {copy.refresh}
          </button>
          <button type="button" onClick={() => void refreshPermissions()}>
            {copy.checkPermissions}
          </button>
          <button type="button" onClick={() => void refreshPerformance()}>
            {copy.refreshMetrics}
          </button>
          <button type="button" onClick={() => void startRecording()}>
            {copy.start}
          </button>
          <button type="button" onClick={() => void stopRecording()}>
            {copy.stopAndFlush}
          </button>
        </div>
        <div className="runtime-meta">
          <p>
            <strong>{copy.backend}:</strong>{" "}
            {status
              ? `${status.service} ${status.version} (${status.ready ? copy.ready : copy.notReady})`
              : copy.loading}
          </p>
          <p>
            <strong>{copy.state}:</strong>{" "}
            <span className="state-inline">{translateRecordingState(recordingState, uiLocale)}</span>
          </p>
        </div>
        {recordingError ? <p className="error">{copy.errorPrefix}: {recordingError}</p> : null}
      </section>

      {permissions ? (
        <section className="card">
          <h2>{copy.permissionHealth}</h2>
          <p>
            <strong>{copy.microphone}:</strong>{" "}
            <span className={`perm perm-${permissions.microphone}`}>
              {translatePermissionState(permissions.microphone, uiLocale)}
            </span>
          </p>
          <p>
            <strong>{copy.accessibility}:</strong>{" "}
            <span className={`perm perm-${permissions.accessibility}`}>
              {translatePermissionState(permissions.accessibility, uiLocale)}
            </span>
          </p>
          <p>{permissions.guidance.join(" ")}</p>
        </section>
      ) : null}

      {performance ? (
        <section className="card">
          <h2>{copy.performanceReport}</h2>
          <div className="perf-grid">
            <p>
              <strong>{copy.audioP95}:</strong> {performance.audioProcessing.p95Ms}ms
            </p>
            <p>
              <strong>{copy.networkP95}:</strong> {performance.networkSend.p95Ms}ms
            </p>
            <p>
              <strong>{copy.injectionP95}:</strong> {performance.injection.p95Ms}ms
            </p>
            <p>
              <strong>{copy.endToEndP95}:</strong> {performance.endToEnd.p95Ms}ms
            </p>
          </div>
          <p>
            <strong>{copy.sent}:</strong> {performance.sentAudioChunks} chunks in {performance.sentAudioBatches} batches
          </p>
          <p>
            <strong>{copy.dropped}:</strong> {copy.audio} {performance.droppedAudioChunks}, {copy.committed}{" "}
            {performance.droppedCommittedTranscripts}
          </p>
          {performance.warnings.length > 0 ? (
            <p className="error">{performance.warnings.join(" ")}</p>
          ) : (
            <p>{copy.allTrackedGood}</p>
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
          uiLocale={uiLocale}
          stateLabel={recordingState}
          partialTranscript={partialTranscript}
          committedTranscript={committedTranscript}
          errorMessage={recordingError}
        />
      ) : (
        <section className="card overlay-hidden">
          <h2>{copy.overlayHidden}</h2>
          <p>{copy.overlayHiddenHint}</p>
        </section>
      )}

      <SettingsPanel
        uiLocale={uiLocale}
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
