import React, { useState, useEffect } from 'react';
import {
  Bell,
  Shield,
  Send,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Globe,
  ExternalLink,
  KeyRound,
  Trash2,
  MessageSquare,
  HelpCircle,
  Clock,
} from 'lucide-react';
import { api } from '../services/api';
import {
  MonitorSummary,
  JudgeNotificationChannel,
  NotificationOutboxItem,
} from '../types';

interface JudgeNotificationsViewProps {
  monitors: MonitorSummary[];
  onNavigateToMonitor?: (id: string, tab?: string) => void;
}

export const JudgeNotificationsView: React.FC<JudgeNotificationsViewProps> = ({
  monitors,
  onNavigateToMonitor,
}) => {
  const [selectedMonitorId, setSelectedMonitorId] = useState<string>(() => {
    return monitors.length > 0 ? monitors[0].id : '';
  });

  const [loading, setLoading] = useState<boolean>(true);
  const [outboxLoading, setOutboxLoading] = useState<boolean>(false);
  const [channels, setChannels] = useState<{
    discord?: JudgeNotificationChannel | null;
    telegram?: JudgeNotificationChannel | null;
  }>({});
  const [outboxItems, setOutboxItems] = useState<NotificationOutboxItem[]>([]);

  // Discord Form State
  const [discordUrl, setDiscordUrl] = useState<string>('');
  const [discordEnabled, setDiscordEnabled] = useState<boolean>(false);
  const [discordTesting, setDiscordTesting] = useState<boolean>(false);
  const [discordVerifying, setDiscordVerifying] = useState<boolean>(false);
  const [discordCodeInput, setDiscordCodeInput] = useState<string>('');
  const [discordPendingVerification, setDiscordPendingVerification] = useState<boolean>(false);
  const [discordMsg, setDiscordMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Telegram Form State
  const [tgToken, setTgToken] = useState<string>('');
  const [tgChatId, setTgChatId] = useState<string>('');
  const [tgEnabled, setTgEnabled] = useState<boolean>(false);
  const [tgTesting, setTgTesting] = useState<boolean>(false);
  const [tgVerifying, setTgVerifying] = useState<boolean>(false);
  const [tgCodeInput, setTgCodeInput] = useState<string>('');
  const [tgPendingVerification, setTgPendingVerification] = useState<boolean>(false);
  const [tgMsg, setTgMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [showTgGuide, setShowTgGuide] = useState<boolean>(false);

  const [savingChannel, setSavingChannel] = useState<string | null>(null);

  useEffect(() => {
    if (monitors.length > 0 && !selectedMonitorId) {
      setSelectedMonitorId(monitors[0].id);
    }
  }, [monitors, selectedMonitorId]);

  useEffect(() => {
    loadSettings();
    loadOutbox();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const data = await api.getJudgeNotificationSettings();
      setChannels(data.channels || {});

      if (data.channels.discord) {
        setDiscordEnabled(data.channels.discord.enabled);
        setDiscordUrl(data.channels.discord.configuration?.webhook_url || '');
        if (data.channels.discord.monitor_id) {
          setSelectedMonitorId(data.channels.discord.monitor_id);
        }
      }

      if (data.channels.telegram) {
        setTgEnabled(data.channels.telegram.enabled);
        setTgToken(data.channels.telegram.configuration?.bot_token || '');
        setTgChatId(data.channels.telegram.configuration?.chat_id || '');
        if (data.channels.telegram.monitor_id && !data.channels.discord) {
          setSelectedMonitorId(data.channels.telegram.monitor_id);
        }
      }
    } catch (err: unknown) {
      console.error('Failed to load judge notification settings:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadOutbox = async () => {
    try {
      setOutboxLoading(true);
      const items = await api.getNotificationOutbox(50);
      setOutboxItems(items);
    } catch (err: unknown) {
      console.error('Failed to load judge outbox:', err);
    } finally {
      setOutboxLoading(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Discord Handlers
  // ---------------------------------------------------------------------------
  const handleSaveDiscord = async () => {
    if (!selectedMonitorId) {
      setDiscordMsg({ type: 'error', text: 'Please select a target monitor first.' });
      return;
    }
    setSavingChannel('discord');
    setDiscordMsg(null);
    try {
      await api.updateJudgeNotificationChannel('discord', {
        monitor_id: selectedMonitorId,
        configuration: { webhook_url: discordUrl },
        enabled: discordEnabled,
      });
      setDiscordMsg({ type: 'success', text: 'Discord configuration saved.' });
      loadSettings();
    } catch (err: unknown) {
      setDiscordMsg({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to save Discord settings.',
      });
    } finally {
      setSavingChannel(null);
    }
  };

  const handleTestDiscord = async () => {
    if (!selectedMonitorId) {
      setDiscordMsg({ type: 'error', text: 'Please select a target monitor first.' });
      return;
    }
    if (!discordUrl.trim()) {
      setDiscordMsg({ type: 'error', text: 'Discord webhook URL is required.' });
      return;
    }
    setDiscordTesting(true);
    setDiscordMsg(null);
    try {
      const res = await api.testJudgeNotificationChannel('discord', {
        monitor_id: selectedMonitorId,
        configuration: { webhook_url: discordUrl },
      });
      setDiscordPendingVerification(true);
      setDiscordMsg({
        type: 'success',
        text: res.message || 'Test notification dispatched! Check your Discord channel for your verification code.',
      });
      loadSettings();
      loadOutbox();
    } catch (err: unknown) {
      setDiscordMsg({
        type: 'error',
        text: err instanceof Error ? err.message : 'Test notification delivery failed.',
      });
    } finally {
      setDiscordTesting(false);
    }
  };

  const handleVerifyDiscord = async () => {
    if (!selectedMonitorId) return;
    if (!discordCodeInput.trim()) {
      setDiscordMsg({ type: 'error', text: 'Please enter the 6-character verification code.' });
      return;
    }
    setDiscordVerifying(true);
    setDiscordMsg(null);
    try {
      const res = await api.verifyJudgeNotificationChannel('discord', {
        monitor_id: selectedMonitorId,
        code: discordCodeInput.trim(),
      });
      setDiscordPendingVerification(false);
      setDiscordCodeInput('');
      setDiscordEnabled(true);
      setDiscordMsg({
        type: 'success',
        text: res.message || 'Destination verified and change alerts activated!',
      });
      loadSettings();
      loadOutbox();
    } catch (err: unknown) {
      setDiscordMsg({
        type: 'error',
        text: err instanceof Error ? err.message : 'Verification failed.',
      });
    } finally {
      setDiscordVerifying(false);
    }
  };

  const handleDeleteDiscord = async () => {
    if (!window.confirm('Remove Discord notification channel from your evaluation session?')) return;
    try {
      await api.deleteJudgeNotificationChannel('discord');
      setDiscordUrl('');
      setDiscordEnabled(false);
      setDiscordPendingVerification(false);
      setDiscordMsg({ type: 'success', text: 'Discord channel removed.' });
      loadSettings();
    } catch (err: unknown) {
      setDiscordMsg({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to delete channel.',
      });
    }
  };

  // ---------------------------------------------------------------------------
  // Telegram Handlers
  // ---------------------------------------------------------------------------
  const handleSaveTelegram = async () => {
    if (!selectedMonitorId) {
      setTgMsg({ type: 'error', text: 'Please select a target monitor first.' });
      return;
    }
    setSavingChannel('telegram');
    setTgMsg(null);
    try {
      await api.updateJudgeNotificationChannel('telegram', {
        monitor_id: selectedMonitorId,
        configuration: { bot_token: tgToken, chat_id: tgChatId },
        enabled: tgEnabled,
      });
      setTgMsg({ type: 'success', text: 'Telegram configuration saved.' });
      loadSettings();
    } catch (err: unknown) {
      setTgMsg({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to save Telegram settings.',
      });
    } finally {
      setSavingChannel(null);
    }
  };

  const handleTestTelegram = async () => {
    if (!selectedMonitorId) {
      setTgMsg({ type: 'error', text: 'Please select a target monitor first.' });
      return;
    }
    if (!tgToken.trim() || !tgChatId.trim()) {
      setTgMsg({ type: 'error', text: 'Telegram bot_token and chat_id are required.' });
      return;
    }
    setTgTesting(true);
    setTgMsg(null);
    try {
      const res = await api.testJudgeNotificationChannel('telegram', {
        monitor_id: selectedMonitorId,
        configuration: { bot_token: tgToken, chat_id: tgChatId },
      });
      setTgPendingVerification(true);
      setTgMsg({
        type: 'success',
        text: res.message || 'Test notification dispatched! Check your Telegram chat for your verification code.',
      });
      loadSettings();
      loadOutbox();
    } catch (err: unknown) {
      setTgMsg({
        type: 'error',
        text: err instanceof Error ? err.message : 'Test notification delivery failed.',
      });
    } finally {
      setTgTesting(false);
    }
  };

  const handleVerifyTelegram = async () => {
    if (!selectedMonitorId) return;
    if (!tgCodeInput.trim()) {
      setTgMsg({ type: 'error', text: 'Please enter the 6-character verification code.' });
      return;
    }
    setTgVerifying(true);
    setTgMsg(null);
    try {
      const res = await api.verifyJudgeNotificationChannel('telegram', {
        monitor_id: selectedMonitorId,
        code: tgCodeInput.trim(),
      });
      setTgPendingVerification(false);
      setTgCodeInput('');
      setTgEnabled(true);
      setTgMsg({
        type: 'success',
        text: res.message || 'Telegram destination verified and change alerts activated!',
      });
      loadSettings();
      loadOutbox();
    } catch (err: unknown) {
      setTgMsg({
        type: 'error',
        text: err instanceof Error ? err.message : 'Verification failed.',
      });
    } finally {
      setTgVerifying(false);
    }
  };

  const handleDeleteTelegram = async () => {
    if (!window.confirm('Remove Telegram notification channel from your evaluation session?')) return;
    try {
      await api.deleteJudgeNotificationChannel('telegram');
      setTgToken('');
      setTgChatId('');
      setTgEnabled(false);
      setTgPendingVerification(false);
      setTgMsg({ type: 'success', text: 'Telegram channel removed.' });
      loadSettings();
    } catch (err: unknown) {
      setTgMsg({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to delete channel.',
      });
    }
  };

  const isDiscordVerified = channels.discord?.is_verified ?? false;
  const isTgVerified = channels.telegram?.is_verified ?? false;

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-6 border-b border-[#40372D]">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-xs font-mono font-medium uppercase tracking-widest text-[#C5A474]">
              Evaluation Observability
            </span>
            <span className="text-[10px] bg-[#342B20] text-[#C5A474] border border-[#C5A474]/30 px-2 py-0.5 rounded-full font-mono">
              Anonymous Session
            </span>
          </div>
          <h1 className="font-serif text-3xl font-medium tracking-tight text-[#F5EFE5] mt-1">
            External Alerts & Notifications
          </h1>
          <p className="text-sm text-[#BDB3A7] mt-1.5 max-w-2xl font-sans">
            Connect real Discord webhooks or Telegram bots to receive instant external alerts whenever a monitored webpage has confirmed semantic or visual changes.
          </p>
        </div>

        <div className="mt-4 sm:mt-0 flex items-center space-x-2">
          <button
            onClick={() => {
              loadSettings();
              loadOutbox();
            }}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 border border-[#40372D] hover:border-[#665744] rounded-lg text-xs font-medium text-[#BDB3A7] hover:text-[#F5EFE5] hover:bg-[#211D19] transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-[#C5A474] ${loading || outboxLoading ? 'animate-spin' : ''}`} />
            <span>Refresh Status</span>
          </button>
        </div>
      </div>

      {/* Target Monitor Selection Banner */}
      {monitors.length === 0 ? (
        <div className="bg-[#211D19] border border-[#E9AD5A]/40 rounded-xl p-5 shadow-sm">
          <div className="flex items-start space-x-3.5">
            <div className="w-8 h-8 rounded-lg bg-[#342B20] border border-[#E9AD5A]/40 text-[#E9AD5A] flex items-center justify-center shrink-0 mt-0.5">
              <AlertCircle className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-[#F5EFE5]">No Website Monitors Created Yet</h4>
              <p className="text-xs text-[#BDB3A7] mt-1 leading-relaxed">
                External alert channels are associated with monitors in your evaluation session. Please add a target website using the "+ Add Website" button before configuring alert delivery.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-[#1A1714] border border-[#40372D] rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-[#211D19] border border-[#40372D] text-[#C5A474] flex items-center justify-center">
              <Globe className="w-4 h-4" />
            </div>
            <div>
              <div className="text-xs font-mono text-[#8F8579] uppercase">Alert Source Monitor</div>
              <div className="text-sm font-medium text-[#F5EFE5]">
                {monitors.find((m) => m.id === selectedMonitorId)?.name || 'Select Monitor'}
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <label className="text-xs text-[#8F8579] font-sans">Target:</label>
            <select
              value={selectedMonitorId}
              onChange={(e) => setSelectedMonitorId(e.target.value)}
              className="bg-[#211D19] border border-[#40372D] rounded-lg px-3 py-1.5 text-xs text-[#F5EFE5] focus:outline-none focus:border-[#C5A474]"
            >
              {monitors.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} ({m.url.replace(/^https?:\/\//, '').slice(0, 30)})
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* Security & Verification Explanation Notice */}
      <div className="bg-[#100F0D] border border-[#40372D]/60 rounded-xl p-4 text-xs text-[#8F8579] flex items-start space-x-3">
        <Shield className="w-4 h-4 text-[#C5A474] shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-semibold text-[#BDB3A7]">Proof of Control & SSRF Protection:</span>{' '}
          To prevent unchecked public spam and arbitrary outbound requests, webhooks must be verified using a test ping before external alerts can be activated. Credentials are encrypted at rest with Fernet and automatically destroyed when your session expires.
        </div>
      </div>

      {/* Notification Providers Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ===================================================================
            1. DISCORD WEBHOOK CARD
           =================================================================== */}
        <div className="bg-[#211D19] border border-[#40372D] rounded-2xl p-6 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-4 border-b border-[#40372D]/60 mb-5">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-[#5865F2]/10 border border-[#5865F2]/30 flex items-center justify-center text-[#5865F2]">
                  <MessageSquare className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-serif text-lg font-medium text-[#F5EFE5]">Discord Webhook</h3>
                  <p className="text-xs text-[#8F8579]">Real-time embeds on change detection</p>
                </div>
              </div>

              {/* Status Badge */}
              <div>
                {isDiscordVerified && discordEnabled ? (
                  <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-medium bg-[#34C59A]/10 text-[#34C59A] border border-[#34C59A]/30">
                    <CheckCircle2 className="w-3 h-3" />
                    <span>Active</span>
                  </span>
                ) : isDiscordVerified ? (
                  <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-medium bg-[#8F8579]/10 text-[#8F8579] border border-[#8F8579]/30">
                    <span>Verified (Paused)</span>
                  </span>
                ) : (
                  <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-medium bg-[#E9AD5A]/10 text-[#E9AD5A] border border-[#E9AD5A]/30">
                    <span>Test Required</span>
                  </span>
                )}
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-[#BDB3A7] mb-1.5">
                  Discord Webhook URL
                </label>
                <input
                  type="text"
                  value={discordUrl}
                  onChange={(e) => {
                    setDiscordUrl(e.target.value);
                    setDiscordPendingVerification(false);
                  }}
                  placeholder="https://discord.com/api/webhooks/..."
                  className="w-full bg-[#141210] border border-[#40372D] rounded-xl px-3.5 py-2.5 text-xs text-[#F5EFE5] font-mono placeholder-[#8F8579]/50 focus:outline-none focus:border-[#C5A474]"
                />
                <span className="text-[10px] text-[#8F8579] mt-1 block">
                  Must be an official Discord webhook endpoint (https://discord.com/api/webhooks/...)
                </span>
              </div>

              {/* Verification Code Box (Visible after Test Ping) */}
              {discordPendingVerification && (
                <div className="bg-[#141210] border border-[#C5A474]/50 rounded-xl p-4 space-y-3 animate-fadeIn">
                  <div className="flex items-start space-x-2.5">
                    <KeyRound className="w-4 h-4 text-[#C5A474] shrink-0 mt-0.5" />
                    <div>
                      <div className="text-xs font-semibold text-[#F5EFE5]">
                        Enter 6-Character Verification Code
                      </div>
                      <p className="text-[11px] text-[#BDB3A7] mt-0.5">
                        A test notification was dispatched to Discord containing a 6-character code. Enter it below to prove destination control.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <input
                      type="text"
                      maxLength={8}
                      value={discordCodeInput}
                      onChange={(e) => setDiscordCodeInput(e.target.value.toUpperCase())}
                      placeholder="e.g. 4A9E2B"
                      className="bg-[#211D19] border border-[#40372D] rounded-lg px-3 py-1.5 text-xs font-mono text-[#F5EFE5] tracking-widest uppercase w-36 text-center focus:outline-none focus:border-[#C5A474]"
                    />
                    <button
                      onClick={handleVerifyDiscord}
                      disabled={discordVerifying || !discordCodeInput.trim()}
                      className="inline-flex items-center space-x-1.5 bg-[#C5A474] hover:bg-[#D8BB8E] text-[#141210] font-semibold text-xs px-3.5 py-1.5 rounded-lg shadow-gold transition-all disabled:opacity-50"
                    >
                      {discordVerifying ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                      <span>Confirm & Activate</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Channel Enablement Toggle (Only active once verified) */}
              <div className="flex items-center justify-between pt-2">
                <div>
                  <span className="text-xs font-medium text-[#F5EFE5] block">Enable Automatic Alerts</span>
                  <span className="text-[10px] text-[#8F8579]">
                    {isDiscordVerified 
                      ? 'Dispatches alerts when this monitor confirms a CHANGED state.'
                      : 'Requires successful test ping & code confirmation first.'}
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={discordEnabled}
                  disabled={!isDiscordVerified}
                  onChange={(e) => setDiscordEnabled(e.target.checked)}
                  className="w-4 h-4 rounded border-[#40372D] bg-[#141210] text-[#C5A474] focus:ring-0 disabled:opacity-30 cursor-pointer"
                />
              </div>

              {discordMsg && (
                <div
                  className={`p-3 rounded-xl text-xs flex items-start space-x-2 ${
                    discordMsg.type === 'success'
                      ? 'bg-[#34C59A]/10 text-[#34C59A] border border-[#34C59A]/30'
                      : 'bg-[#ED7777]/10 text-[#ED7777] border border-[#ED7777]/30'
                  }`}
                >
                  {discordMsg.type === 'success' ? (
                    <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                  ) : (
                    <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  )}
                  <span>{discordMsg.text}</span>
                </div>
              )}
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-[#40372D]/60 flex items-center justify-between">
            <button
              onClick={handleTestDiscord}
              disabled={discordTesting || !discordUrl.trim()}
              className="inline-flex items-center space-x-1.5 bg-[#211D19] border border-[#40372D] hover:border-[#665744] text-[#BDB3A7] hover:text-[#F5EFE5] px-3.5 py-2 rounded-xl text-xs font-medium transition-all disabled:opacity-50"
            >
              <Send className={`w-3.5 h-3.5 text-[#C5A474] ${discordTesting ? 'animate-spin' : ''}`} />
              <span>{discordTesting ? 'Dispatching...' : 'Send Test Ping'}</span>
            </button>

            <div className="flex items-center space-x-2">
              {channels.discord && (
                <button
                  onClick={handleDeleteDiscord}
                  title="Remove Discord channel"
                  className="p-2 border border-[#ED7777]/30 hover:border-[#ED7777]/60 text-[#ED7777] hover:bg-[#ED7777]/10 rounded-xl text-xs transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
              <button
                onClick={handleSaveDiscord}
                disabled={savingChannel === 'discord' || !discordUrl.trim()}
                className="inline-flex items-center space-x-1.5 bg-[#C5A474] hover:bg-[#D8BB8E] text-[#141210] font-semibold text-xs px-4 py-2 rounded-xl shadow-gold transition-all disabled:opacity-50"
              >
                {savingChannel === 'discord' && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                <span>Save</span>
              </button>
            </div>
          </div>
        </div>

        {/* ===================================================================
            2. TELEGRAM BOT CARD
           =================================================================== */}
        <div className="bg-[#211D19] border border-[#40372D] rounded-2xl p-6 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-4 border-b border-[#40372D]/60 mb-5">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-[#229ED9]/10 border border-[#229ED9]/30 flex items-center justify-center text-[#229ED9]">
                  <Send className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-serif text-lg font-medium text-[#F5EFE5]">Telegram Bot</h3>
                  <p className="text-xs text-[#8F8579]">Instant messages to chats or channels</p>
                </div>
              </div>

              {/* Status Badge */}
              <div>
                {isTgVerified && tgEnabled ? (
                  <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-medium bg-[#34C59A]/10 text-[#34C59A] border border-[#34C59A]/30">
                    <CheckCircle2 className="w-3 h-3" />
                    <span>Active</span>
                  </span>
                ) : isTgVerified ? (
                  <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-medium bg-[#8F8579]/10 text-[#8F8579] border border-[#8F8579]/30">
                    <span>Verified (Paused)</span>
                  </span>
                ) : (
                  <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-medium bg-[#E9AD5A]/10 text-[#E9AD5A] border border-[#E9AD5A]/30">
                    <span>Test Required</span>
                  </span>
                )}
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-medium text-[#BDB3A7]">
                    Bot API Token
                  </label>
                  <button
                    onClick={() => setShowTgGuide(!showTgGuide)}
                    className="text-[10px] text-[#C5A474] hover:underline flex items-center space-x-0.5"
                  >
                    <HelpCircle className="w-3 h-3" />
                    <span>Setup Guide</span>
                  </button>
                </div>
                <input
                  type="text"
                  value={tgToken}
                  onChange={(e) => {
                    setTgToken(e.target.value);
                    setTgPendingVerification(false);
                  }}
                  placeholder="123456789:ABCdefGHIjklmnop..."
                  className="w-full bg-[#141210] border border-[#40372D] rounded-xl px-3.5 py-2.5 text-xs text-[#F5EFE5] font-mono placeholder-[#8F8579]/50 focus:outline-none focus:border-[#C5A474]"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-[#BDB3A7] mb-1.5">
                  Target Chat ID / Channel Username
                </label>
                <input
                  type="text"
                  value={tgChatId}
                  onChange={(e) => {
                    setTgChatId(e.target.value);
                    setTgPendingVerification(false);
                  }}
                  placeholder="e.g. 987654321 or @your_channel"
                  className="w-full bg-[#141210] border border-[#40372D] rounded-xl px-3.5 py-2.5 text-xs text-[#F5EFE5] font-mono placeholder-[#8F8579]/50 focus:outline-none focus:border-[#C5A474]"
                />
              </div>

              {/* Setup Guide Collapsible */}
              {showTgGuide && (
                <div className="bg-[#141210] border border-[#40372D] rounded-xl p-3 text-xs text-[#BDB3A7] space-y-1.5">
                  <div className="font-semibold text-[#F5EFE5]">Quick Telegram Bot Setup:</div>
                  <ol className="list-decimal list-inside space-y-1 text-[11px] text-[#8F8579]">
                    <li>Open Telegram and message <strong className="text-[#C5A474]">@BotFather</strong> to create a new bot (<code className="text-[#F5EFE5]">/newbot</code>).</li>
                    <li>Copy the HTTP API token into the Token field above.</li>
                    <li>Start a chat with your bot (or add it as admin to your channel).</li>
                    <li>Send a test ping below to receive your 6-character verification code.</li>
                  </ol>
                </div>
              )}

              {/* Verification Code Box */}
              {tgPendingVerification && (
                <div className="bg-[#141210] border border-[#C5A474]/50 rounded-xl p-4 space-y-3 animate-fadeIn">
                  <div className="flex items-start space-x-2.5">
                    <KeyRound className="w-4 h-4 text-[#C5A474] shrink-0 mt-0.5" />
                    <div>
                      <div className="text-xs font-semibold text-[#F5EFE5]">
                        Enter 6-Character Verification Code
                      </div>
                      <p className="text-[11px] text-[#BDB3A7] mt-0.5">
                        A test notification was dispatched to Telegram containing a 6-character code. Enter it below to prove destination control.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <input
                      type="text"
                      maxLength={8}
                      value={tgCodeInput}
                      onChange={(e) => setTgCodeInput(e.target.value.toUpperCase())}
                      placeholder="e.g. B7D3A1"
                      className="bg-[#211D19] border border-[#40372D] rounded-lg px-3 py-1.5 text-xs font-mono text-[#F5EFE5] tracking-widest uppercase w-36 text-center focus:outline-none focus:border-[#C5A474]"
                    />
                    <button
                      onClick={handleVerifyTelegram}
                      disabled={tgVerifying || !tgCodeInput.trim()}
                      className="inline-flex items-center space-x-1.5 bg-[#C5A474] hover:bg-[#D8BB8E] text-[#141210] font-semibold text-xs px-3.5 py-1.5 rounded-lg shadow-gold transition-all disabled:opacity-50"
                    >
                      {tgVerifying ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                      <span>Confirm & Activate</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Channel Enablement Toggle */}
              <div className="flex items-center justify-between pt-2">
                <div>
                  <span className="text-xs font-medium text-[#F5EFE5] block">Enable Automatic Alerts</span>
                  <span className="text-[10px] text-[#8F8579]">
                    {isTgVerified 
                      ? 'Dispatches alerts when this monitor confirms a CHANGED state.'
                      : 'Requires successful test ping & code confirmation first.'}
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={tgEnabled}
                  disabled={!isTgVerified}
                  onChange={(e) => setTgEnabled(e.target.checked)}
                  className="w-4 h-4 rounded border-[#40372D] bg-[#141210] text-[#C5A474] focus:ring-0 disabled:opacity-30 cursor-pointer"
                />
              </div>

              {tgMsg && (
                <div
                  className={`p-3 rounded-xl text-xs flex items-start space-x-2 ${
                    tgMsg.type === 'success'
                      ? 'bg-[#34C59A]/10 text-[#34C59A] border border-[#34C59A]/30'
                      : 'bg-[#ED7777]/10 text-[#ED7777] border border-[#ED7777]/30'
                  }`}
                >
                  {tgMsg.type === 'success' ? (
                    <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                  ) : (
                    <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  )}
                  <span>{tgMsg.text}</span>
                </div>
              )}
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-[#40372D]/60 flex items-center justify-between">
            <button
              onClick={handleTestTelegram}
              disabled={tgTesting || !tgToken.trim() || !tgChatId.trim()}
              className="inline-flex items-center space-x-1.5 bg-[#211D19] border border-[#40372D] hover:border-[#665744] text-[#BDB3A7] hover:text-[#F5EFE5] px-3.5 py-2 rounded-xl text-xs font-medium transition-all disabled:opacity-50"
            >
              <Send className={`w-3.5 h-3.5 text-[#C5A474] ${tgTesting ? 'animate-spin' : ''}`} />
              <span>{tgTesting ? 'Dispatching...' : 'Send Test Ping'}</span>
            </button>

            <div className="flex items-center space-x-2">
              {channels.telegram && (
                <button
                  onClick={handleDeleteTelegram}
                  title="Remove Telegram channel"
                  className="p-2 border border-[#ED7777]/30 hover:border-[#ED7777]/60 text-[#ED7777] hover:bg-[#ED7777]/10 rounded-xl text-xs transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
              <button
                onClick={handleSaveTelegram}
                disabled={savingChannel === 'telegram' || !tgToken.trim() || !tgChatId.trim()}
                className="inline-flex items-center space-x-1.5 bg-[#C5A474] hover:bg-[#D8BB8E] text-[#141210] font-semibold text-xs px-4 py-2 rounded-xl shadow-gold transition-all disabled:opacity-50"
              >
                {savingChannel === 'telegram' && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                <span>Save</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* =====================================================================
          3. DELIVERY OUTBOX & AUDIT LOG TABLE (Requirement 9)
         ===================================================================== */}
      <div className="bg-[#211D19] border border-[#40372D] rounded-2xl p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-[#40372D]/60 mb-5 gap-3">
          <div>
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-[#C5A474]" />
              <h3 className="font-serif text-lg font-medium text-[#F5EFE5]">
                Alert Delivery Outbox & History
              </h3>
            </div>
            <p className="text-xs text-[#8F8579] mt-0.5">
              Live external notification dispatch status, retry attempts, and delivery logs.
            </p>
          </div>

          <button
            onClick={loadOutbox}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 border border-[#40372D] hover:border-[#665744] rounded-lg text-xs font-medium text-[#BDB3A7] hover:text-[#F5EFE5] hover:bg-[#1A1714] transition-colors self-start sm:self-auto"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-[#C5A474] ${outboxLoading ? 'animate-spin' : ''}`} />
            <span>Refresh Outbox</span>
          </button>
        </div>

        {outboxItems.length === 0 ? (
          <div className="py-12 text-center text-xs text-[#8F8579]">
            <Bell className="w-8 h-8 mx-auto text-[#40372D] mb-2" />
            <p className="font-medium text-[#BDB3A7]">No alerts generated yet in this session.</p>
            <p className="text-[11px] mt-1 text-[#8F8579]">
              Alerts are dispatched only when a monitored website detects confirmed content changes.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#1A1714] text-[#8F8579] uppercase font-mono text-[10px] tracking-wider border-b border-[#40372D]">
                <tr>
                  <th className="px-4 py-3">Monitor</th>
                  <th className="px-4 py-3">Channel</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Attempts</th>
                  <th className="px-4 py-3">Details / Error</th>
                  <th className="px-4 py-3 text-right">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#40372D]/40">
                {outboxItems.map((item) => (
                  <tr key={item.id} className="hover:bg-[#1A1714]/40 transition-colors">
                    <td className="px-4 py-3 font-medium text-[#F5EFE5]">
                      <div className="flex items-center space-x-2">
                        <span>{item.monitor_name || 'Monitor'}</span>
                        {item.monitor_id && onNavigateToMonitor && (
                          <button
                            onClick={() => onNavigateToMonitor(item.monitor_id, 'overview')}
                            className="text-[#C5A474] hover:text-[#D8BB8E]"
                            title="Inspect Monitor"
                          >
                            <ExternalLink className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-[#BDB3A7] uppercase">
                      <span className="px-2 py-0.5 rounded bg-[#141210] border border-[#40372D] text-[10px]">
                        {item.channel_type}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {item.state === 'sent' ? (
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-mono bg-[#34C59A]/10 text-[#34C59A] border border-[#34C59A]/30">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>SENT</span>
                        </span>
                      ) : item.state === 'sending' ? (
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-mono bg-[#635BFF]/10 text-[#635BFF] border border-[#635BFF]/30">
                          <RefreshCw className="w-3 h-3 animate-spin" />
                          <span>SENDING</span>
                        </span>
                      ) : item.state === 'failed' ? (
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-mono bg-[#ED7777]/10 text-[#ED7777] border border-[#ED7777]/30">
                          <AlertCircle className="w-3 h-3" />
                          <span>FAILED</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-mono bg-[#E9AD5A]/10 text-[#E9AD5A] border border-[#E9AD5A]/30">
                          <Clock className="w-3 h-3" />
                          <span>PENDING</span>
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 font-mono text-[#8F8579]">
                      {item.attempts} {item.attempts === 1 ? 'try' : 'tries'}
                    </td>
                    <td className="px-4 py-3 text-[#8F8579] max-w-xs truncate font-mono text-[11px]">
                      {item.last_error ? (
                        <span className="text-[#ED7777]" title={item.last_error}>
                          {item.last_error}
                        </span>
                      ) : (
                        <span className="text-[#34C59A]">Delivered successfully</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-[#8F8579] text-[11px]">
                      {new Date(item.sent_at || item.created_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
