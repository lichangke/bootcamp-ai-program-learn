type OverlayWindowProps = {
  stateLabel: string;
  partialTranscript: string;
  committedTranscript: string;
  errorMessage: string;
};

function stateDescriptor(stateLabel: string): { className: string; text: string; hint: string } {
  switch (stateLabel) {
    case "Connecting":
      return { className: "state-connecting", text: "Connecting", hint: "Building websocket session..." };
    case "Listening":
      return { className: "state-listening", text: "Listening", hint: "Microphone ready, waiting for voice." };
    case "Recording":
      return { className: "state-recording", text: "Recording", hint: "Capturing and streaming audio." };
    case "Processing":
      return { className: "state-processing", text: "Processing", hint: "Finalizing speech recognition." };
    case "Injecting":
      return { className: "state-injecting", text: "Injecting", hint: "Typing text into active app." };
    case "Error":
      return { className: "state-error", text: "Error", hint: "Action required before continuing." };
    default:
      return { className: "state-idle", text: "Idle", hint: "Press the hotkey to begin." };
  }
}

export function OverlayWindow({
  stateLabel,
  partialTranscript,
  committedTranscript,
  errorMessage,
}: OverlayWindowProps) {
  const descriptor = stateDescriptor(stateLabel);
  const partialPreview = partialTranscript.trim() ? partialTranscript : "Waiting for realtime transcript...";
  const committedPreview = committedTranscript.trim() ? committedTranscript : "No committed transcript yet.";

  return (
    <section className="card overlay-card">
      <div className="overlay-head">
        <h2>Overlay Preview</h2>
        <span className={`state-badge ${descriptor.className}`}>{descriptor.text}</span>
      </div>
      <p className="overlay-hint">{descriptor.hint}</p>
      <div className="overlay-body">
        <p className="mono transcript-block">
          <strong>Partial</strong>
          <span>{partialPreview}</span>
        </p>
        <p className="mono transcript-block">
          <strong>Committed</strong>
          <span>{committedPreview}</span>
        </p>
      </div>
      {errorMessage ? <p className="error">Error: {errorMessage}</p> : null}
    </section>
  );
}
