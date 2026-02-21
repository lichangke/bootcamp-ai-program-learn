export type SettingsDraft = {
  apiKey: string;
  languageCode: string;
  hotkey: string;
  injectionThreshold: number;
  partialRewriteEnabled: boolean;
  partialRewriteMaxBackspace: number;
  partialRewriteWindowMs: number;
};

type SettingsPanelProps = {
  uiLocale: "en" | "zh";
  settings: SettingsDraft;
  onApiKeyChange: (value: string) => void;
  onLanguageChange: (value: string) => void;
  onHotkeyChange: (value: string) => void;
  onInjectionThresholdChange: (value: number) => void;
  onPartialRewriteEnabledChange: (value: boolean) => void;
  onPartialRewriteMaxBackspaceChange: (value: number) => void;
  onPartialRewriteWindowMsChange: (value: number) => void;
  onSave: () => void;
  isSaving: boolean;
  saveMessage: string;
  saveError: string;
};

export function SettingsPanel({
  uiLocale,
  settings,
  onApiKeyChange,
  onLanguageChange,
  onHotkeyChange,
  onInjectionThresholdChange,
  onPartialRewriteEnabledChange,
  onPartialRewriteMaxBackspaceChange,
  onPartialRewriteWindowMsChange,
  onSave,
  isSaving,
  saveMessage,
  saveError,
}: SettingsPanelProps) {
  const zh = uiLocale === "zh";

  return (
    <section className="card">
      <h2>{zh ? "设置" : "Settings"}</h2>
      <div className="settings-grid">
        <label htmlFor="api-key">{zh ? "ElevenLabs API Key" : "ElevenLabs API Key"}</label>
        <input
          id="api-key"
          value={settings.apiKey}
          onChange={(event) => onApiKeyChange(event.target.value)}
          placeholder={zh ? "粘贴 API key" : "Paste API key"}
          type="password"
          autoComplete="off"
        />
        <label htmlFor="language">{zh ? "识别语言" : "Language Code"}</label>
        <select
          id="language"
          value={settings.languageCode}
          onChange={(event) => onLanguageChange(event.target.value)}
        >
          <option value="eng">{zh ? "英文 (eng)" : "English (eng)"}</option>
          <option value="zho">{zh ? "简体中文 (zho)" : "Simplified Chinese (zho)"}</option>
        </select>
        <label htmlFor="hotkey">{zh ? "全局热键" : "Global Hotkey"}</label>
        <input
          id="hotkey"
          value={settings.hotkey}
          onChange={(event) => onHotkeyChange(event.target.value)}
          placeholder="Ctrl+N"
          spellCheck={false}
        />
        <label htmlFor="threshold">{zh ? "注入阈值" : "Injection Threshold"}</label>
        <input
          id="threshold"
          value={settings.injectionThreshold}
          onChange={(event) => onInjectionThresholdChange(Number(event.target.value))}
          min={1}
          max={1024}
          step={1}
          type="number"
        />
        <label htmlFor="partial-rewrite-enabled">{zh ? "Partial 回改" : "Partial Rewrite"}</label>
        <input
          id="partial-rewrite-enabled"
          checked={settings.partialRewriteEnabled}
          onChange={(event) => onPartialRewriteEnabledChange(event.target.checked)}
          type="checkbox"
        />
        <label htmlFor="partial-rewrite-backspace">
          {zh ? "回改最大退格数" : "Rewrite Max Backspace"}
        </label>
        <input
          id="partial-rewrite-backspace"
          value={settings.partialRewriteMaxBackspace}
          onChange={(event) => onPartialRewriteMaxBackspaceChange(Number(event.target.value))}
          min={0}
          max={64}
          step={1}
          type="number"
        />
        <label htmlFor="partial-rewrite-window">
          {zh ? "回改节流窗口 (ms)" : "Rewrite Window (ms)"}
        </label>
        <input
          id="partial-rewrite-window"
          value={settings.partialRewriteWindowMs}
          onChange={(event) => onPartialRewriteWindowMsChange(Number(event.target.value))}
          min={0}
          max={2000}
          step={10}
          type="number"
        />
      </div>
      <div className="row">
        <button type="button" onClick={onSave} disabled={isSaving}>
          {isSaving ? (zh ? "保存中..." : "Saving...") : zh ? "保存设置" : "Save Settings"}
        </button>
      </div>
      <p className="settings-hint">
        {zh ? (
          <>
            识别语言支持英文和简体中文。热键示例: <code>Ctrl+N</code>, <code>Shift+Alt+R</code>,{" "}
            <code>Cmd+Shift+N</code>。Partial 回改会在实时文本漂移时进行受控的退格并重输。
          </>
        ) : (
          <>
            Language supports English and Simplified Chinese. Hotkey examples: <code>Ctrl+N</code>,{" "}
            <code>Shift+Alt+R</code>, <code>Cmd+Shift+N</code>. Partial rewrite applies controlled
            backspace-and-retype correction for realtime transcript drift.
          </>
        )}
      </p>
      <div className="settings-explain">
        {zh ? (
          <>
            <p>
              <strong>注入阈值:</strong> 小于这个字数时，优先逐字输入；达到或超过这个值时，优先走剪贴板粘贴。
            </p>
            <p>
              <strong>回改最大退格数:</strong> 每次实时纠错最多回删多少个字符。值越大，纠错更积极；值越小，更稳但改得少。
            </p>
            <p>
              <strong>回改节流窗口 (ms):</strong> 两次回改之间的最小间隔。越小反应越快，越大抖动越少。
            </p>
            <p>
              <strong>推荐值:</strong> <code>10 / 12 / 140</code> 适合大多数场景；<code>8 / 8 / 180</code>{" "}
              更稳。
            </p>
          </>
        ) : (
          <>
            <p>
              <strong>Injection Threshold:</strong> Below this length, text is typed directly; at or above it,
              clipboard paste is preferred.
            </p>
            <p>
              <strong>Rewrite Max Backspace:</strong> Maximum characters deleted in one realtime correction.
              Higher is more aggressive; lower is more stable.
            </p>
            <p>
              <strong>Rewrite Window (ms):</strong> Minimum interval between two rewrites. Smaller reacts faster;
              larger reduces jitter.
            </p>
            <p>
              <strong>Recommended:</strong> <code>10 / 12 / 140</code> fits most cases;{" "}
              <code>8 / 8 / 180</code> is more stable.
            </p>
          </>
        )}
      </div>
      {saveError ? <p className="error">{zh ? "错误" : "Error"}: {saveError}</p> : null}
      {saveMessage ? <p>{saveMessage}</p> : null}
    </section>
  );
}
