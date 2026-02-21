export type SettingsDraft = {
  apiKey: string;
  languageCode: string;
  hotkey: string;
  injectionThreshold: number;
};

type SettingsPanelProps = {
  settings: SettingsDraft;
  onApiKeyChange: (value: string) => void;
  onLanguageChange: (value: string) => void;
  onHotkeyChange: (value: string) => void;
  onInjectionThresholdChange: (value: number) => void;
  onSave: () => void;
  isSaving: boolean;
  saveMessage: string;
  saveError: string;
};

export function SettingsPanel({
  settings,
  onApiKeyChange,
  onLanguageChange,
  onHotkeyChange,
  onInjectionThresholdChange,
  onSave,
  isSaving,
  saveMessage,
  saveError,
}: SettingsPanelProps) {
  return (
    <section className="card">
      <h2>Settings</h2>
      <div className="settings-grid">
        <label htmlFor="api-key">ElevenLabs API Key</label>
        <input
          id="api-key"
          value={settings.apiKey}
          onChange={(event) => onApiKeyChange(event.target.value)}
          placeholder="Paste API key"
          type="password"
          autoComplete="off"
        />
        <label htmlFor="language">Language Code</label>
        <select
          id="language"
          value={settings.languageCode}
          onChange={(event) => onLanguageChange(event.target.value)}
        >
          <option value="eng">English (eng)</option>
          <option value="zho">Chinese (zho)</option>
        </select>
        <label htmlFor="hotkey">Global Hotkey</label>
        <input
          id="hotkey"
          value={settings.hotkey}
          onChange={(event) => onHotkeyChange(event.target.value)}
          placeholder="Ctrl+N"
          spellCheck={false}
        />
        <label htmlFor="threshold">Injection Threshold</label>
        <input
          id="threshold"
          value={settings.injectionThreshold}
          onChange={(event) => onInjectionThresholdChange(Number(event.target.value))}
          min={1}
          max={1024}
          step={1}
          type="number"
        />
      </div>
      <div className="row">
        <button type="button" onClick={onSave} disabled={isSaving}>
          {isSaving ? "Saving..." : "Save Settings"}
        </button>
      </div>
      <p className="settings-hint">
        Language supports English and Chinese. Hotkey examples: <code>Ctrl+N</code>,{" "}
        <code>Shift+Alt+R</code>, <code>Cmd+Shift+N</code>.
      </p>
      {saveError ? <p className="error">Error: {saveError}</p> : null}
      {saveMessage ? <p>{saveMessage}</p> : null}
    </section>
  );
}
