import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { NotificationChannel, NotificationOutboxItem } from '../types';

export const SettingsView: React.FC = () => {
  const [, setSettings] = useState<Record<string, NotificationChannel>>({});
  const [outboxItems, setOutboxItems] = useState<NotificationOutboxItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [outboxLoading, setOutboxLoading] = useState(false);
  const [outboxFilter, setOutboxFilter] = useState('all');

  // Form states
  const [discordUrl, setDiscordUrl] = useState('');
  const [discordEnabled, setDiscordEnabled] = useState(false);
  const [discordTesting, setDiscordTesting] = useState(false);
  const [discordMsg, setDiscordMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [tgToken, setTgToken] = useState('');
  const [tgChatId, setTgChatId] = useState('');
  const [tgEnabled, setTgEnabled] = useState(false);
  const [tgTesting, setTgTesting] = useState(false);
  const [tgMsg, setTgMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [smtpHost, setSmtpHost] = useState('');
  const [smtpPort, setSmtpPort] = useState('587');
  const [smtpUser, setSmtpUser] = useState('');
  const [smtpPass, setSmtpPass] = useState('');
  const [smtpTls, setSmtpTls] = useState(true);
  const [fromEmail, setFromEmail] = useState('');
  const [toEmail, setToEmail] = useState('');
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [emailTesting, setEmailTesting] = useState(false);
  const [emailMsg, setEmailMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [savingChannel, setSavingChannel] = useState<string | null>(null);

  useEffect(() => {
    loadSettings();
    loadOutbox();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const data = await api.getNotificationSettings();
      setSettings(data);

      if (data.discord) {
        setDiscordEnabled(data.discord.enabled);
        setDiscordUrl(data.discord.configuration?.webhook_url || '');
      }
      if (data.telegram) {
        setTgEnabled(data.telegram.enabled);
        setTgToken(data.telegram.configuration?.bot_token || '');
        setTgChatId(data.telegram.configuration?.chat_id || '');
      }
      if (data.email) {
        const c = data.email.configuration || {};
        setEmailEnabled(data.email.enabled);
        setSmtpHost(c.smtp_host || '');
        setSmtpPort(String(c.smtp_port || 587));
        setSmtpUser(c.smtp_user || '');
        setSmtpPass(c.smtp_password || '');
        setSmtpTls(c.smtp_tls !== false);
        setFromEmail(c.from_email || '');
        setToEmail(c.to_email || '');
      }
    } catch (e: any) {
      console.error('Failed to load settings:', e);
    } finally {
      setLoading(false);
    }
  };

  const loadOutbox = async () => {
    setOutboxLoading(true);
    try {
      const data = await api.getNotificationOutbox(50, outboxFilter);
      setOutboxItems(data);
    } catch (e) {
      console.error('Failed to load outbox:', e);
    } finally {
      setOutboxLoading(false);
    }
  };

  const saveDiscord = async () => {
    setSavingChannel('discord');
    setDiscordMsg(null);
    try {
      await api.updateNotificationSettings('discord', {
        enabled: discordEnabled,
        configuration: { webhook_url: discordUrl },
      });
      setDiscordMsg({ type: 'success', text: 'Discord configuration saved.' });
      loadSettings();
    } catch (e: any) {
      setDiscordMsg({ type: 'error', text: e.message || 'Failed to save Discord settings.' });
    } finally {
      setSavingChannel(null);
    }
  };

  const testDiscord = async () => {
    setDiscordTesting(true);
    setDiscordMsg(null);
    try {
      const res = await api.testNotification('discord', { webhook_url: discordUrl });
      if (res.success) {
        setDiscordMsg({ type: 'success', text: res.message });
      } else {
        setDiscordMsg({ type: 'error', text: res.message });
      }
      loadOutbox();
    } catch (e: any) {
      setDiscordMsg({ type: 'error', text: e.message || 'Discord test failed.' });
    } finally {
      setDiscordTesting(false);
    }
  };

  const saveTelegram = async () => {
    setSavingChannel('telegram');
    setTgMsg(null);
    try {
      await api.updateNotificationSettings('telegram', {
        enabled: tgEnabled,
        configuration: { bot_token: tgToken, chat_id: tgChatId },
      });
      setTgMsg({ type: 'success', text: 'Telegram configuration saved.' });
      loadSettings();
    } catch (e: any) {
      setTgMsg({ type: 'error', text: e.message || 'Failed to save Telegram settings.' });
    } finally {
      setSavingChannel(null);
    }
  };

  const testTelegram = async () => {
    setTgTesting(true);
    setTgMsg(null);
    try {
      const res = await api.testNotification('telegram', { bot_token: tgToken, chat_id: tgChatId });
      if (res.success) {
        setTgMsg({ type: 'success', text: res.message });
      } else {
        setTgMsg({ type: 'error', text: res.message });
      }
      loadOutbox();
    } catch (e: any) {
      setTgMsg({ type: 'error', text: e.message || 'Telegram test failed.' });
    } finally {
      setTgTesting(false);
    }
  };

  const saveEmail = async () => {
    setSavingChannel('email');
    setEmailMsg(null);
    try {
      await api.updateNotificationSettings('email', {
        enabled: emailEnabled,
        configuration: {
          smtp_host: smtpHost,
          smtp_port: parseInt(smtpPort, 10) || 587,
          smtp_user: smtpUser,
          smtp_password: smtpPass,
          smtp_tls: smtpTls,
          from_email: fromEmail,
          to_email: toEmail,
        },
      });
      setEmailMsg({ type: 'success', text: 'Email configuration saved.' });
      loadSettings();
    } catch (e: any) {
      setEmailMsg({ type: 'error', text: e.message || 'Failed to save Email settings.' });
    } finally {
      setSavingChannel(null);
    }
  };

  const testEmail = async () => {
    setEmailTesting(true);
    setEmailMsg(null);
    try {
      const res = await api.testNotification('email', {
        smtp_host: smtpHost,
        smtp_port: parseInt(smtpPort, 10) || 587,
        smtp_user: smtpUser,
        smtp_password: smtpPass,
        smtp_tls: smtpTls,
        from_email: fromEmail,
        to_email: toEmail,
      });
      if (res.success) {
        setEmailMsg({ type: 'success', text: res.message });
      } else {
        setEmailMsg({ type: 'error', text: res.message });
      }
      loadOutbox();
    } catch (e: any) {
      setEmailMsg({ type: 'error', text: e.message || 'Email test failed.' });
    } finally {
      setEmailTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-text-subtle">
        <svg className="animate-spin h-6 w-6 mr-3 text-gold-champagne" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
        Loading notification settings...
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-5xl">
      {/* Header */}
      <div>
        <h2 className="text-xl font-serif font-medium text-ivory-warm">Notification Dispatch & Webhooks</h2>
        <p className="text-xs text-text-subtle mt-1">
          Configure external alert channels. Sensitive tokens and credentials are encrypted at rest using authenticated AES encryption and securely masked.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Discord Card */}
        <div className="bg-surface-elevated border border-warmborder rounded-2xl shadow-luxury p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-2">
                <span className="text-xl">💬</span>
                <h3 className="font-serif font-medium text-ivory-warm">Discord</h3>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={discordEnabled}
                  onChange={(e) => setDiscordEnabled(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-surface-interactive border border-warmborder peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-obsidian-deep after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-ivory-warm after:border-warmborder after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-gold-champagne"></div>
              </label>
            </div>
            <p className="text-xs text-text-subtle mb-4">
              Sends rich embeds to a Discord channel when website content changes.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-text-muted mb-1">Webhook URL</label>
                <input
                  type="text"
                  placeholder="https://discord.com/api/webhooks/..."
                  value={discordUrl}
                  onChange={(e) => setDiscordUrl(e.target.value)}
                  className="w-full text-xs font-mono px-3 py-2 bg-surface-interactive border border-warmborder rounded-xl text-ivory-warm placeholder:text-text-subtle focus:border-gold-champagne/60 focus:outline-none transition-colors"
                />
              </div>

              {discordMsg && (
                <div
                  className={`text-xs p-2.5 rounded-xl ${
                    discordMsg.type === 'success' ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-300 border border-rose-500/20'
                  }`}
                >
                  {discordMsg.text}
                </div>
              )}
            </div>
          </div>

          <div className="pt-6 flex items-center space-x-2 border-t border-warmborder/40 mt-6">
            <button
              onClick={testDiscord}
              disabled={discordTesting || !discordUrl}
              className="flex-1 text-xs font-medium py-2 px-3 border border-warmborder rounded-xl hover:bg-surface-interactive bg-surface-interactive/60 text-ivory-warm disabled:opacity-40 transition-colors"
            >
              {discordTesting ? 'Testing...' : 'Test'}
            </button>
            <button
              onClick={saveDiscord}
              disabled={savingChannel === 'discord'}
              className="flex-1 text-xs font-medium py-2 px-3 bg-gold-champagne hover:bg-gold-hover text-obsidian-deep rounded-xl shadow-gold disabled:opacity-40 transition-all"
            >
              {savingChannel === 'discord' ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>

        {/* Telegram Card */}
        <div className="bg-surface-elevated border border-warmborder rounded-2xl shadow-luxury p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-2">
                <span className="text-xl">✈️</span>
                <h3 className="font-serif font-medium text-ivory-warm">Telegram</h3>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={tgEnabled}
                  onChange={(e) => setTgEnabled(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-surface-interactive border border-warmborder peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-obsidian-deep after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-ivory-warm after:border-warmborder after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-gold-champagne"></div>
              </label>
            </div>
            <p className="text-xs text-text-subtle mb-4">
              Delivers instant HTML formatted notifications via Telegram Bot.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-text-muted mb-1">Bot Token</label>
                <input
                  type="password"
                  placeholder="123456789:ABCdefGhI..."
                  value={tgToken}
                  onChange={(e) => setTgToken(e.target.value)}
                  className="w-full text-xs font-mono px-3 py-2 bg-surface-interactive border border-warmborder rounded-xl text-ivory-warm placeholder:text-text-subtle focus:border-gold-champagne/60 focus:outline-none transition-colors"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-text-muted mb-1">Chat ID</label>
                <input
                  type="text"
                  placeholder="-100123456789"
                  value={tgChatId}
                  onChange={(e) => setTgChatId(e.target.value)}
                  className="w-full text-xs font-mono px-3 py-2 bg-surface-interactive border border-warmborder rounded-xl text-ivory-warm placeholder:text-text-subtle focus:border-gold-champagne/60 focus:outline-none transition-colors"
                />
              </div>

              {tgMsg && (
                <div
                  className={`text-xs p-2.5 rounded-xl ${
                    tgMsg.type === 'success' ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-300 border border-rose-500/20'
                  }`}
                >
                  {tgMsg.text}
                </div>
              )}
            </div>
          </div>

          <div className="pt-6 flex items-center space-x-2 border-t border-warmborder/40 mt-6">
            <button
              onClick={testTelegram}
              disabled={tgTesting || !tgToken || !tgChatId}
              className="flex-1 text-xs font-medium py-2 px-3 border border-warmborder rounded-xl hover:bg-surface-interactive bg-surface-interactive/60 text-ivory-warm disabled:opacity-40 transition-colors"
            >
              {tgTesting ? 'Testing...' : 'Test'}
            </button>
            <button
              onClick={saveTelegram}
              disabled={savingChannel === 'telegram'}
              className="flex-1 text-xs font-medium py-2 px-3 bg-gold-champagne hover:bg-gold-hover text-obsidian-deep rounded-xl shadow-gold disabled:opacity-40 transition-all"
            >
              {savingChannel === 'telegram' ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>

        {/* Email SMTP Card */}
        <div className="bg-surface-elevated border border-warmborder rounded-2xl shadow-luxury p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-2">
                <span className="text-xl">📧</span>
                <h3 className="font-serif font-medium text-ivory-warm">Email (SMTP)</h3>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={emailEnabled}
                  onChange={(e) => setEmailEnabled(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-surface-interactive border border-warmborder peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-obsidian-deep after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-ivory-warm after:border-warmborder after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-gold-champagne"></div>
              </label>
            </div>
            <p className="text-xs text-text-subtle mb-4">
              Delivers HTML change summaries using custom SMTP credentials.
            </p>

            <div className="space-y-2">
              <div className="grid grid-cols-3 gap-2">
                <div className="col-span-2">
                  <label className="block text-[11px] font-medium text-text-muted mb-1">Host</label>
                  <input
                    type="text"
                    placeholder="smtp.mail.com"
                    value={smtpHost}
                    onChange={(e) => setSmtpHost(e.target.value)}
                    className="w-full text-xs px-2.5 py-1.5 bg-surface-interactive border border-warmborder rounded-xl text-ivory-warm placeholder:text-text-subtle focus:border-gold-champagne/60 focus:outline-none transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-text-muted mb-1">Port</label>
                  <input
                    type="number"
                    value={smtpPort}
                    onChange={(e) => setSmtpPort(e.target.value)}
                    className="w-full text-xs px-2.5 py-1.5 bg-surface-interactive border border-warmborder rounded-xl text-ivory-warm placeholder:text-text-subtle focus:border-gold-champagne/60 focus:outline-none transition-colors"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-medium text-text-muted mb-1">Username</label>
                <input
                  type="text"
                  placeholder="alerts@mycorp.com"
                  value={smtpUser}
                  onChange={(e) => setSmtpUser(e.target.value)}
                  className="w-full text-xs px-2.5 py-1.5 bg-surface-interactive border border-warmborder rounded-xl text-ivory-warm placeholder:text-text-subtle focus:border-gold-champagne/60 focus:outline-none transition-colors"
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-text-muted mb-1">Password</label>
                <input
                  type="password"
                  placeholder="••••••••"
                  value={smtpPass}
                  onChange={(e) => setSmtpPass(e.target.value)}
                  className="w-full text-xs px-2.5 py-1.5 bg-surface-interactive border border-warmborder rounded-xl text-ivory-warm placeholder:text-text-subtle focus:border-gold-champagne/60 focus:outline-none transition-colors"
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-text-muted mb-1">Destination Email</label>
                <input
                  type="email"
                  placeholder="admin@mycorp.com"
                  value={toEmail}
                  onChange={(e) => setToEmail(e.target.value)}
                  className="w-full text-xs px-2.5 py-1.5 bg-surface-interactive border border-warmborder rounded-xl text-ivory-warm placeholder:text-text-subtle focus:border-gold-champagne/60 focus:outline-none transition-colors"
                />
              </div>

              {emailMsg && (
                <div
                  className={`text-xs p-2.5 rounded-xl mt-2 ${
                    emailMsg.type === 'success' ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-300 border border-rose-500/20'
                  }`}
                >
                  {emailMsg.text}
                </div>
              )}
            </div>
          </div>

          <div className="pt-6 flex items-center space-x-2 border-t border-warmborder/40 mt-6">
            <button
              onClick={testEmail}
              disabled={emailTesting || !smtpHost || !toEmail}
              className="flex-1 text-xs font-medium py-2 px-3 border border-warmborder rounded-xl hover:bg-surface-interactive bg-surface-interactive/60 text-ivory-warm disabled:opacity-40 transition-colors"
            >
              {emailTesting ? 'Testing...' : 'Test'}
            </button>
            <button
              onClick={saveEmail}
              disabled={savingChannel === 'email'}
              className="flex-1 text-xs font-medium py-2 px-3 bg-gold-champagne hover:bg-gold-hover text-obsidian-deep rounded-xl shadow-gold disabled:opacity-40 transition-all"
            >
              {savingChannel === 'email' ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      </div>

      {/* Outbox Delivery History Table */}
      <div className="bg-surface-elevated border border-warmborder rounded-2xl shadow-luxury overflow-hidden">
        <div className="p-5 border-b border-warmborder flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-obsidian-deep/50">
          <div>
            <h3 className="text-base font-serif font-medium text-ivory-warm">Notification Outbox Audit</h3>
            <p className="text-xs text-text-subtle mt-0.5">
              Durable outbox dispatch logs with bounded retries and external delivery status.
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <select
              value={outboxFilter}
              onChange={(e) => {
                setOutboxFilter(e.target.value);
                setTimeout(loadOutbox, 50);
              }}
              className="text-xs bg-surface-interactive border border-warmborder rounded-xl text-ivory-warm px-3 py-1.5 focus:outline-none focus:border-gold-champagne/60 transition-colors cursor-pointer"
            >
              <option value="all" className="bg-surface-elevated text-ivory-warm">All States</option>
              <option value="sent" className="bg-surface-elevated text-ivory-warm">Delivered (Sent)</option>
              <option value="failed" className="bg-surface-elevated text-ivory-warm">Failed</option>
              <option value="pending" className="bg-surface-elevated text-ivory-warm">Pending</option>
            </select>
            <button
              onClick={loadOutbox}
              disabled={outboxLoading}
              className="p-2 text-text-subtle hover:text-ivory-warm border border-warmborder rounded-xl bg-surface-interactive hover:bg-surface-elevated transition-colors"
              title="Refresh logs"
            >
              <svg className={`w-3.5 h-3.5 ${outboxLoading ? 'animate-spin text-gold-champagne' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          {outboxItems.length === 0 ? (
            <div className="py-12 text-center text-text-subtle text-xs">
              No notification delivery records found.
            </div>
          ) : (
            <table className="min-w-full divide-y divide-warmborder/30 text-left text-xs">
              <thead className="bg-obsidian-deep text-text-subtle font-mono uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3 px-4">Monitor</th>
                  <th className="py-3 px-4">Channel</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Attempts</th>
                  <th className="py-3 px-4">Created</th>
                  <th className="py-3 px-4">Sent At</th>
                  <th className="py-3 px-4">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-warmborder/30 font-normal text-text-muted">
                {outboxItems.map((item) => (
                  <tr key={item.id} className="hover:bg-surface-interactive/30 transition-colors">
                    <td className="py-3 px-4 font-serif font-medium text-ivory-warm">{item.monitor_name}</td>
                    <td className="py-3 px-4 uppercase text-[11px] font-mono font-medium text-gold-champagne">
                      {item.channel_type}
                    </td>
                    <td className="py-3 px-4">
                      {item.state === 'sent' && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                          Delivered
                        </span>
                      )}
                      {item.state === 'failed' && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-rose-500/15 text-rose-400 border border-rose-500/30">
                          Failed
                        </span>
                      )}
                      {item.state === 'pending' && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-500/15 text-amber-300 border border-amber-500/30">
                          Pending
                        </span>
                      )}
                      {item.state === 'sending' && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-gold-champagne/15 text-gold-champagne border border-gold-champagne/30 animate-pulse">
                          Sending
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono">{item.attempts}</td>
                    <td className="py-3 px-4 text-text-subtle font-mono">
                      {new Date(item.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 text-text-subtle font-mono">
                      {item.sent_at ? new Date(item.sent_at).toLocaleString() : '—'}
                    </td>
                    <td className="py-3 px-4 max-w-xs truncate text-text-subtle">
                      {item.last_error ? (
                        <span className="text-rose-400" title={item.last_error}>
                          {item.last_error}
                        </span>
                      ) : (
                        <span className="text-text-subtle font-mono">OK</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};
