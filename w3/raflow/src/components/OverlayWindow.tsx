type OverlayWindowProps = {
  uiLocale: "en" | "zh";
  stateLabel: string;
  partialTranscript: string;
  committedTranscript: string;
  errorMessage: string;
};

function stateDescriptor(
  stateLabel: string,
  uiLocale: "en" | "zh",
): { className: string; text: string; hint: string } {
  const zh = uiLocale === "zh";
  switch (stateLabel) {
    case "Connecting":
      return {
        className: "state-connecting",
        text: zh ? "连接中" : "Connecting",
        hint: zh ? "正在建立 websocket 会话..." : "Building websocket session...",
      };
    case "Listening":
      return {
        className: "state-listening",
        text: zh ? "监听中" : "Listening",
        hint: zh ? "麦克风已就绪，等待语音输入。" : "Microphone ready, waiting for voice.",
      };
    case "Recording":
      return {
        className: "state-recording",
        text: zh ? "录制中" : "Recording",
        hint: zh ? "正在采集并流式传输音频。" : "Capturing and streaming audio.",
      };
    case "Processing":
      return {
        className: "state-processing",
        text: zh ? "处理中" : "Processing",
        hint: zh ? "正在完成语音识别收尾。" : "Finalizing speech recognition.",
      };
    case "Injecting":
      return {
        className: "state-injecting",
        text: zh ? "注入中" : "Injecting",
        hint: zh ? "正在向当前应用输入文本。" : "Typing text into active app.",
      };
    case "Error":
      return {
        className: "state-error",
        text: zh ? "错误" : "Error",
        hint: zh ? "继续前需要先处理问题。" : "Action required before continuing.",
      };
    default:
      return {
        className: "state-idle",
        text: zh ? "空闲" : "Idle",
        hint: zh ? "按下热键开始。" : "Press the hotkey to begin.",
      };
  }
}

export function OverlayWindow({
  uiLocale,
  stateLabel,
  partialTranscript,
  committedTranscript,
  errorMessage,
}: OverlayWindowProps) {
  const descriptor = stateDescriptor(stateLabel, uiLocale);
  const partialPreview = partialTranscript.trim()
    ? partialTranscript
    : uiLocale === "zh"
      ? "等待实时转写..."
      : "Waiting for realtime transcript...";
  const committedPreview = committedTranscript.trim()
    ? committedTranscript
    : uiLocale === "zh"
      ? "尚无 committed 文本。"
      : "No committed transcript yet.";

  return (
    <section className="card overlay-card">
      <div className="overlay-head">
        <h2>{uiLocale === "zh" ? "悬浮窗预览" : "Overlay Preview"}</h2>
        <span className={`state-badge ${descriptor.className}`}>{descriptor.text}</span>
      </div>
      <p className="overlay-hint">{descriptor.hint}</p>
      <div className="overlay-body">
        <p className="mono transcript-block">
          <strong>{uiLocale === "zh" ? "实时 Partial" : "Partial"}</strong>
          <span>{partialPreview}</span>
        </p>
        <p className="mono transcript-block">
          <strong>{uiLocale === "zh" ? "已确认 Committed" : "Committed"}</strong>
          <span>{committedPreview}</span>
        </p>
      </div>
      {errorMessage ? <p className="error">{uiLocale === "zh" ? "错误" : "Error"}: {errorMessage}</p> : null}
    </section>
  );
}
