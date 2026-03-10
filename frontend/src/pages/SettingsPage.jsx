import { useState, useEffect } from 'react';
import { getSettings, updateSettings } from '../api/settings';

/** Format capability key for display (e.g. filesystem_read → Filesystem read). */
function formatCapabilityLabel(key) {
  return key
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

const PERMISSION_OPTIONS = [
  { value: 'allow', label: 'Allow (no prompt)' },
  { value: 'ask', label: 'Ask every time' },
  { value: 'ask_once_per_chat', label: 'Ask once per chat' },
  { value: 'deny', label: 'Deny' },
];

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [defaults, setDefaults] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    getSettings()
      .then((data) => {
        if (!cancelled && data?.permissions?.defaults != null) {
          setDefaults({ ...data.permissions.defaults });
        } else if (!cancelled) {
          setDefaults({});
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const handlePermissionChange = (capability, value) => {
    setDefaults((prev) => (prev ? { ...prev, [capability]: value } : { [capability]: value }));
  };

  const handleSave = () => {
    if (defaults == null) return;
    setSaving(true);
    setError(null);
    updateSettings({ permissions: { defaults } })
      .then((data) => {
        if (data?.permissions?.defaults != null) {
          setDefaults({ ...data.permissions.defaults });
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setSaving(false));
  };

  if (loading) {
    return (
      <div className="settings-page">
        <h1>Settings</h1>
        <p className="page-message">Loading…</p>
      </div>
    );
  }

  const capabilities = defaults != null ? Object.keys(defaults).sort() : [];

  return (
    <div className="settings-page">
      <h1>Settings</h1>
      {error && <p className="page-message error">{error}</p>}

      <section className="settings-section">
        <h2 className="settings-section-title">Tool permissions</h2>
        <p className="settings-section-desc">
          Control whether the assistant can use tools without asking. Capabilities are provided by the server.
        </p>
        {capabilities.length === 0 ? (
          <p className="page-message">No capabilities returned from server.</p>
        ) : (
          <div className="settings-permissions">
            {capabilities.map((cap) => (
              <div key={cap} className="settings-permission-row">
                <label className="settings-permission-label" htmlFor={`perm-${cap}`}>
                  {formatCapabilityLabel(cap)}
                </label>
                <select
                  id={`perm-${cap}`}
                  className="settings-permission-select"
                  value={defaults[cap] ?? 'ask'}
                  onChange={(e) => handlePermissionChange(cap, e.target.value)}
                >
                  {PERMISSION_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            ))}
            <div className="settings-permission-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleSave}
                disabled={saving || defaults == null}
              >
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
