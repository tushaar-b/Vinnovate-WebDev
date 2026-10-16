import React, { useState, useEffect } from 'react';
import {
  Globe,
  ArrowRight,
  Shield,
  Eye,
  Sliders,
  Bell,
  Cpu,
  Lock,
  Key,
  CheckCircle2,
  Sparkles,
  Server,
  Database,
  Layers,
  X,
  RefreshCw,
  AlertCircle,
  Compass,
  ChevronDown,
} from 'lucide-react';
import { HealthStatus } from '../types';

interface LandingPageProps {
  health: HealthStatus | null;
  healthLoading: boolean;
  onEnterNormalUser: () => void;
  onAdminLogin: (password: string) => Promise<void>;
  loginLoading: boolean;
  loginError: string | null;
}

export const LandingPage: React.FC<LandingPageProps> = ({
  health,
  healthLoading,
  onEnterNormalUser,
  onAdminLogin,
  loginLoading,
  loginError,
}) => {
  const [isContinueModalOpen, setIsContinueModalOpen] = useState(false);
  const [adminPassword, setAdminPassword] = useState('');
  const [bottomAdminPassword, setBottomAdminPassword] = useState('');

  useEffect(() => {
    if (typeof window !== 'undefined' && (window.location.hash === '#admin' || window.location.hash === '#login')) {
      scrollToSection('continue-options');
    }
  }, []);

  const handleModalAdminSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!adminPassword.trim()) return;
    await onAdminLogin(adminPassword);
  };

  const handleBottomAdminSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bottomAdminPassword.trim()) return;
    await onAdminLogin(bottomAdminPassword);
  };

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="min-h-screen bg-[#141210] text-[#F5EFE5] font-sans flex flex-col selection:bg-[#C5A474]/20 selection:text-[#F5EFE5]">
      {/* =====================================================================
          1. STICKY TOP NAVBAR
         ===================================================================== */}
      <header className="sticky top-0 z-40 bg-[#100F0D]/90 backdrop-blur-md border-b border-[#40372D] transition-all">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo & Brand */}
          <div
            className="flex items-center space-x-3 cursor-pointer group"
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          >
            <div className="w-10 h-10 rounded-xl bg-[#211D19] border border-[#C5A474]/40 flex items-center justify-center text-[#C5A474] shadow-sm group-hover:border-[#C5A474] transition-all duration-200">
              <Globe className="w-5 h-5" />
            </div>
            <div className="flex flex-col">
              <span className="font-serif font-medium text-lg leading-tight tracking-tight text-[#F5EFE5]">
                Website Change Detector
              </span>
              <span className="text-[10px] text-[#8F8579] font-medium tracking-wider uppercase font-sans">
                Precision Observability
              </span>
            </div>
          </div>

          {/* Center Navigation Links */}
          <nav className="hidden md:flex items-center space-x-7 text-xs font-medium text-[#BDB3A7]">
            <button
              onClick={() => scrollToSection('features')}
              className="hover:text-[#C5A474] transition-colors"
            >
              Capabilities
            </button>
            <button
              onClick={() => scrollToSection('how-it-works')}
              className="hover:text-[#C5A474] transition-colors"
            >
              Workflow
            </button>
            <button
              onClick={() => scrollToSection('preview')}
              className="hover:text-[#C5A474] transition-colors"
            >
              Diff Engine
            </button>
            <button
              onClick={() => scrollToSection('architecture')}
              className="hover:text-[#C5A474] transition-colors"
            >
              Architecture
            </button>
            <button
              onClick={() => scrollToSection('continue-options')}
              className="hover:text-[#C5A474] transition-colors"
            >
              Get Started
            </button>
          </nav>

          {/* Right Action Buttons */}
          <div className="flex items-center space-x-3">
            {/* System Status Pill */}
            <div className="hidden lg:flex items-center space-x-2 text-[11px] bg-[#211D19] border border-[#40372D] px-2.5 py-1 rounded-full text-[#BDB3A7]">
              <span
                className={`w-2 h-2 rounded-full ${
                  health?.status === 'ok' ? 'bg-[#34C59A] animate-pulse' : 'bg-[#E9AD5A]'
                }`}
              />
              <span className="font-medium font-sans">
                {healthLoading ? 'Connecting...' : health?.status === 'ok' ? 'System Online' : 'Checking'}
              </span>
            </div>

            {/* Direct Admin Login Quick-Action */}
            <button
              onClick={() => scrollToSection('continue-options')}
              className="hidden sm:inline-flex items-center space-x-1.5 text-xs font-medium text-[#BDB3A7] hover:text-[#F5EFE5] px-3 py-1.5 rounded-lg border border-[#40372D] hover:border-[#665744] hover:bg-[#211D19] transition-all"
            >
              <Lock className="w-3.5 h-3.5 text-[#C5A474]" />
              <span>Admin Login</span>
            </button>

            {/* Primary Continue Button */}
            <button
              onClick={() => setIsContinueModalOpen(true)}
              className="inline-flex items-center space-x-2 bg-[#C5A474] hover:bg-[#D8BB8E] text-[#141210] text-xs font-semibold px-4 py-2 rounded-xl shadow-gold transition-all transform active:scale-95"
            >
              <span>Continue</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </header>

      {/* =====================================================================
          2. HERO SECTION — FULL VIEWPORT
         ===================================================================== */}
      <section className="relative min-h-[calc(100vh-4rem)] flex flex-col justify-between items-center overflow-hidden px-4 sm:px-6 lg:px-8 text-center">
        {/* Subtle warm atmospheric glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-5xl h-[520px] bg-gradient-to-b from-[#C5A474]/12 via-[#C5A474]/4 to-transparent pointer-events-none -z-10 blur-3xl rounded-full" />

        {/* Top spacer to balance the vertical centering */}
        <div className="hidden sm:block h-6" />

        {/* Centered Hero Content */}
        <div className="max-w-5xl mx-auto my-auto py-12 flex flex-col items-center">
          {/* Main Headline */}
          <h1 className="font-serif text-5xl sm:text-6xl md:text-7xl lg:text-7xl font-normal text-[#F5EFE5] tracking-tight leading-[1.12] max-w-5xl mx-auto">
            Detect Every Website Change.{' '}
            <span className="text-[#C5A474] italic block mt-3 sm:mt-4">
              Down to the Pixel and Word.
            </span>
          </h1>

          {/* Subtitle */}
          <p className="mt-8 text-base sm:text-lg md:text-xl text-[#BDB3A7] max-w-2xl mx-auto leading-relaxed font-sans">
            Track meaningful website changes through real browser captures, noise-aware text extraction, and precise version comparisons.
          </p>

          {/* CTA Group */}
          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4 w-full sm:w-auto">
            {/* Primary Continue Button */}
            <button
              onClick={() => setIsContinueModalOpen(true)}
              className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-8 py-4 bg-[#C5A474] hover:bg-[#D8BB8E] text-[#141210] font-semibold text-sm rounded-xl shadow-gold transition-all transform hover:-translate-y-0.5 active:translate-y-0"
            >
              <span>Continue to Platform</span>
              <ArrowRight className="w-4 h-4" />
            </button>

            {/* Direct Judge Workspace Button (Recommended for evaluators) */}
            <button
              onClick={onEnterNormalUser}
              className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-8 py-4 bg-[#211D19]/80 hover:bg-[#2A2520] text-[#F5EFE5] font-semibold text-sm rounded-xl border border-[#40372D] hover:border-[#665744] shadow-sm transition-all"
            >
              <Compass className="w-4 h-4 text-[#C5A474]" />
              <span>Explore Judge Workspace</span>
              <span className="text-xs font-normal text-[#8F8579]">(No Login)</span>
            </button>
          </div>
        </div>

        {/* Bottom Scroll Indicator */}
        <div
          className="pb-8 pt-4 flex flex-col items-center space-y-1.5 text-[#8F8579] cursor-pointer hover:text-[#C5A474] transition-colors"
          onClick={() => scrollToSection('preview')}
        >
          <span className="text-[10px] font-sans uppercase tracking-widest text-[#8F8579]">Explore Diff Engine</span>
          <ChevronDown className="w-4 h-4 animate-bounce text-[#C5A474]" />
        </div>
      </section>

      {/* =====================================================================
          3. HERO VISUAL PREVIEW MOCKUP SECTION
         ===================================================================== */}
      <section id="preview" className="relative py-24 px-4 sm:px-6 lg:px-8 border-t border-[#40372D]/50 bg-[#100F0D]/40">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <span className="text-xs font-mono font-medium uppercase tracking-widest text-[#C5A474]">Live Difference Engine</span>
            <h2 className="font-serif text-3xl sm:text-4xl lg:text-5xl font-medium text-[#F5EFE5] mt-2">
              Side-by-side baseline intelligence.
            </h2>
            <p className="text-sm sm:text-base text-[#BDB3A7] mt-3 max-w-2xl mx-auto">
              Inspect semantic content additions, price drops, and structural DOM mutations with cryptographic certainty.
            </p>
          </div>

          <div className="max-w-4xl mx-auto rounded-2xl bg-[#211D19] border border-[#40372D] shadow-luxury overflow-hidden transition-all text-left">
            {/* Mockup browser chrome top bar */}
            <div className="bg-[#1A1714] border-b border-[#40372D] px-4 py-2.5 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#ED7777]/80" />
                <span className="w-2.5 h-2.5 rounded-full bg-[#E9AD5A]/80" />
                <span className="w-2.5 h-2.5 rounded-full bg-[#34C59A]/80" />
              </div>
              <div className="bg-[#100F0D] border border-[#40372D] px-4 py-1 rounded-md text-[11px] font-mono text-[#BDB3A7] flex items-center space-x-2 w-72 justify-center">
                <Globe className="w-3 h-3 text-[#8F8579]" />
                <span className="truncate">https://store.example.com/item/pro-15</span>
              </div>
              <div className="flex items-center space-x-2 text-[11px] font-semibold text-[#E9AD5A] bg-[#342B20] border border-[#E9AD5A]/40 px-2.5 py-0.5 rounded-full">
                <span>CHANGE DETECTED</span>
              </div>
            </div>

            {/* Mockup comparison body */}
            <div className="p-6 bg-[#141210]/60">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Version 1 Card */}
                <div className="bg-[#1A1714] border border-[#40372D] rounded-xl p-4 text-left shadow-sm">
                  <div className="flex items-center justify-between pb-3 border-b border-[#40372D]/60">
                    <span className="text-xs font-semibold text-[#BDB3A7]">Baseline Version (v1)</span>
                    <span className="text-[10px] bg-[#211D19] text-[#8F8579] border border-[#40372D] px-2 py-0.5 rounded font-mono">10:00 AM</span>
                  </div>
                  <div className="mt-3 space-y-2">
                    <div className="text-xs font-medium text-[#F5EFE5]">Ultra-Lightweight Developer Laptop 15"</div>
                    <div className="p-2.5 rounded-lg bg-[#141210] border border-[#40372D] text-xs">
                      <div className="text-[#8F8579] line-through font-mono">Stock: In Stock (42 units)</div>
                      <div className="text-base font-serif font-bold text-[#F5EFE5] mt-1">$1,299.00 USD</div>
                    </div>
                  </div>
                </div>

                {/* Version 2 Card (Changed) */}
                <div className="bg-[#211D19] border-2 border-[#C5A474] rounded-xl p-4 text-left shadow-luxury relative">
                  <div className="absolute -top-2.5 right-4 bg-[#C5A474] text-[#141210] text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">
                    Difference Verified
                  </div>
                  <div className="flex items-center justify-between pb-3 border-b border-[#40372D]/60">
                    <span className="text-xs font-bold text-[#C5A474]">Captured Snapshot (v2)</span>
                    <span className="text-[10px] bg-[#342B20] text-[#C5A474] border border-[#C5A474]/30 px-2 py-0.5 rounded font-mono">10:15 AM</span>
                  </div>
                  <div className="mt-3 space-y-2">
                    <div className="text-xs font-medium text-[#F5EFE5]">Ultra-Lightweight Developer Laptop 15"</div>
                    <div className="p-2.5 rounded-lg bg-[#141210] border border-[#34C59A]/30 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-[#34C59A] font-medium text-[11px]">Price Drop Detected (-23%)</span>
                        <span className="text-[#ED7777] line-through text-[11px] font-mono">$1,299.00</span>
                      </div>
                      <div className="text-xl font-serif font-bold text-[#34C59A] mt-0.5">$999.00 USD</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Verified Text Diff Chip Strip */}
              <div className="mt-4 p-3 bg-[#1A1714] border border-[#40372D] rounded-xl flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="flex items-center space-x-2">
                  <span className="text-[#8F8579] font-medium">Text Delta:</span>
                  <span className="px-2 py-0.5 bg-[#ED7777]/10 text-[#ED7777] border border-[#ED7777]/30 rounded font-mono text-[11px] line-through">
                    - $1,299.00
                  </span>
                  <span className="px-2 py-0.5 bg-[#34C59A]/10 text-[#34C59A] border border-[#34C59A]/30 rounded font-mono text-[11px] font-semibold">
                    + $999.00
                  </span>
                </div>
                <div className="text-[11px] text-[#8F8579] font-mono">
                  SHA-256: <span className="text-[#F5EFE5] font-semibold">e4b7...910a</span>
                </div>
              </div>
              <div className="mt-2 text-right">
                <span className="text-[10px] text-[#8F8579] italic font-sans">
                  * Illustrative diff preview — add target URL below to capture live page data.
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =====================================================================
          3. METRICS / STATS STRIP
         ===================================================================== */}
      <section className="border-y border-[#40372D] bg-[#100F0D] py-10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          <div>
            <div className="text-3xl sm:text-4xl font-serif font-normal text-[#F5EFE5]">0% Noise</div>
            <div className="text-xs text-[#BDB3A7] mt-1.5 font-medium">Tracking script & telemetry exclusion</div>
          </div>
          <div>
            <div className="text-3xl sm:text-4xl font-serif font-normal text-[#F5EFE5]">Playwright</div>
            <div className="text-xs text-[#BDB3A7] mt-1.5 font-medium">Headless Chromium full-viewport captures</div>
          </div>
          <div>
            <div className="text-3xl sm:text-4xl font-serif font-normal text-[#F5EFE5]">SHA-256</div>
            <div className="text-xs text-[#BDB3A7] mt-1.5 font-medium">Normalized cryptographic content hashing</div>
          </div>
          <div>
            <div className="text-3xl sm:text-4xl font-serif font-normal text-[#F5EFE5]">PostgreSQL</div>
            <div className="text-xs text-[#BDB3A7] mt-1.5 font-medium">VersionArtifact binary persistence</div>
          </div>
        </div>
      </section>

      {/* =====================================================================
          4. CORE FEATURES SECTION
         ===================================================================== */}
      <section id="features" className="py-24 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <div className="text-xs font-semibold uppercase tracking-wider text-[#C5A474] mb-2 font-sans">Capabilities</div>
          <h2 className="font-serif text-3xl sm:text-4xl font-normal text-[#F5EFE5] tracking-tight">
            Engineered for Precision Observability
          </h2>
          <p className="mt-3.5 text-sm text-[#BDB3A7] leading-relaxed">
            Eliminate noisy alerts and cosmetic false alarms. Inspect verified visual differences and human-readable text modifications.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1 */}
          <div className="bg-[#211D19] border border-[#40372D] hover:border-[#665744] rounded-2xl p-7 shadow-sm transition-all duration-200">
            <div className="w-11 h-11 rounded-xl bg-[#342B20] border border-[#C5A474]/30 text-[#C5A474] flex items-center justify-center mb-5">
              <Cpu className="w-5 h-5" />
            </div>
            <h3 className="font-serif text-lg font-medium text-[#F5EFE5]">Real Headless Chromium Engine</h3>
            <p className="text-xs text-[#BDB3A7] mt-2.5 leading-relaxed font-sans">
              Executes client-side JavaScript, handles dynamic single-page applications, and captures full-resolution viewport snapshots using Playwright.
            </p>
          </div>

          {/* Card 2 */}
          <div className="bg-[#211D19] border border-[#40372D] hover:border-[#665744] rounded-2xl p-7 shadow-sm transition-all duration-200">
            <div className="w-11 h-11 rounded-xl bg-[#342B20] border border-[#C5A474]/30 text-[#C5A474] flex items-center justify-center mb-5">
              <Eye className="w-5 h-5" />
            </div>
            <h3 className="font-serif text-lg font-medium text-[#F5EFE5]">Noise & Telemetry Exclusion</h3>
            <p className="text-xs text-[#BDB3A7] mt-2.5 leading-relaxed font-sans">
              Intelligent DOM parsing strips ad trackers, request IDs, cache tokens, and ephemeral configuration variables before diff calculation.
            </p>
          </div>

          {/* Card 3 */}
          <div className="bg-[#211D19] border border-[#40372D] hover:border-[#665744] rounded-2xl p-7 shadow-sm transition-all duration-200">
            <div className="w-11 h-11 rounded-xl bg-[#342B20] border border-[#C5A474]/30 text-[#C5A474] flex items-center justify-center mb-5">
              <Layers className="w-5 h-5" />
            </div>
            <h3 className="font-serif text-lg font-medium text-[#F5EFE5]">Side-by-Side & Overlay Diff</h3>
            <p className="text-xs text-[#BDB3A7] mt-2.5 leading-relaxed font-sans">
              Compare versions visually with interactive slider overlays or inspect word-by-word additions and deletions in human-readable color blocks.
            </p>
          </div>

          {/* Card 4 */}
          <div className="bg-[#211D19] border border-[#40372D] hover:border-[#665744] rounded-2xl p-7 shadow-sm transition-all duration-200">
            <div className="w-11 h-11 rounded-xl bg-[#342B20] border border-[#C5A474]/30 text-[#C5A474] flex items-center justify-center mb-5">
              <Sliders className="w-5 h-5" />
            </div>
            <h3 className="font-serif text-lg font-medium text-[#F5EFE5]">Visual CSS Region Picker</h3>
            <p className="text-xs text-[#BDB3A7] mt-2.5 leading-relaxed font-sans">
              Visually highlight and click on elements to generate WATCH or IGNORE CSS selectors. Suppress noisy headers or isolate prices with ease.
            </p>
          </div>

          {/* Card 5 */}
          <div className="bg-[#211D19] border border-[#40372D] hover:border-[#665744] rounded-2xl p-7 shadow-sm transition-all duration-200">
            <div className="w-11 h-11 rounded-xl bg-[#342B20] border border-[#C5A474]/30 text-[#C5A474] flex items-center justify-center mb-5">
              <Bell className="w-5 h-5" />
            </div>
            <h3 className="font-serif text-lg font-medium text-[#F5EFE5]">Encrypted Notifications</h3>
            <p className="text-xs text-[#BDB3A7] mt-2.5 leading-relaxed font-sans">
              Dispatch confirmed change events directly to Discord webhooks, Telegram bots, or SMTP mailboxes with credentials encrypted at rest with Fernet.
            </p>
          </div>

          {/* Card 6 */}
          <div className="bg-[#211D19] border border-[#40372D] hover:border-[#665744] rounded-2xl p-7 shadow-sm transition-all duration-200">
            <div className="w-11 h-11 rounded-xl bg-[#342B20] border border-[#C5A474]/30 text-[#C5A474] flex items-center justify-center mb-5">
              <Shield className="w-5 h-5" />
            </div>
            <h3 className="font-serif text-lg font-medium text-[#F5EFE5]">Enterprise SSRF & Quota Defenses</h3>
            <p className="text-xs text-[#BDB3A7] mt-2.5 leading-relaxed font-sans">
              Strict destination validation rejects loopbacks, cloud metadata (169.254.169.254), private ranges, and non-standard ports to protect infrastructure.
            </p>
          </div>
        </div>
      </section>

      {/* =====================================================================
          5. HOW IT WORKS 3-STEP SECTION
         ===================================================================== */}
      <section id="how-it-works" className="py-24 bg-[#100F0D] border-y border-[#40372D]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <div className="text-xs font-semibold uppercase tracking-wider text-[#C5A474] mb-2 font-sans">Workflow</div>
            <h2 className="font-serif text-3xl sm:text-4xl font-normal text-[#F5EFE5] tracking-tight">
              Three Steps from URL to Verified Change
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
            {/* Step 1 */}
            <div className="bg-[#211D19] border border-[#40372D] rounded-2xl p-8 shadow-sm relative">
              <div className="w-10 h-10 rounded-full bg-[#C5A474] text-[#141210] font-bold font-serif text-sm flex items-center justify-center mb-5">
                1
              </div>
              <h3 className="font-serif text-lg font-medium text-[#F5EFE5]">Add Target URL</h3>
              <p className="text-xs text-[#BDB3A7] mt-2.5 leading-relaxed font-sans">
                Enter any publicly reachable HTTP/HTTPS website. Configure desired check frequency and optional custom region selectors.
              </p>
            </div>

            {/* Step 2 */}
            <div className="bg-[#211D19] border border-[#40372D] rounded-2xl p-8 shadow-sm relative">
              <div className="w-10 h-10 rounded-full bg-[#342B20] text-[#C5A474] border border-[#665744] font-bold font-serif text-sm flex items-center justify-center mb-5">
                2
              </div>
              <h3 className="font-serif text-lg font-medium text-[#F5EFE5]">Headless Playwright Capture</h3>
              <p className="text-xs text-[#BDB3A7] mt-2.5 leading-relaxed font-sans">
                Asynchronous Redis workers boot headless Chromium, execute page scripts, store full-viewport screenshot artifacts, and normalize text.
              </p>
            </div>

            {/* Step 3 */}
            <div className="bg-[#211D19] border border-[#40372D] rounded-2xl p-8 shadow-sm relative">
              <div className="w-10 h-10 rounded-full bg-[#C5A474] text-[#141210] font-bold font-serif text-sm flex items-center justify-center mb-5">
                3
              </div>
              <h3 className="font-serif text-lg font-medium text-[#F5EFE5]">Diff & Alert</h3>
              <p className="text-xs text-[#BDB3A7] mt-2.5 leading-relaxed font-sans">
                The engine evaluates cryptographic SHA-256 deltas. If meaningful content changed, version snapshots and visual overlays are generated.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* =====================================================================
          6. ARCHITECTURE SECTION
         ===================================================================== */}
      <section id="architecture" className="py-24 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto mb-14">
          <div className="text-xs font-semibold uppercase tracking-wider text-[#C5A474] mb-2 font-sans">Distributed Stack</div>
          <h2 className="font-serif text-3xl sm:text-4xl font-normal text-[#F5EFE5] tracking-tight">
            Built for Scalability and Reliability
          </h2>
          <p className="mt-3.5 text-sm text-[#BDB3A7]">
            Separated API, worker, scheduler, and persistent database storage.
          </p>
        </div>

        <div className="bg-[#211D19] border border-[#40372D] rounded-2xl p-8 shadow-luxury">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-5 text-center">
            <div className="p-5 rounded-xl bg-[#100F0D] border border-[#40372D] hover:border-[#665744] transition-all">
              <Globe className="w-6 h-6 text-[#C5A474] mx-auto mb-3" />
              <div className="text-xs font-semibold text-[#F5EFE5]">React + Vite SPA</div>
              <div className="text-[11px] text-[#8F8579] mt-1">Hosted on Vercel</div>
            </div>
            <div className="p-5 rounded-xl bg-[#100F0D] border border-[#40372D] hover:border-[#665744] transition-all">
              <Server className="w-6 h-6 text-[#C5A474] mx-auto mb-3" />
              <div className="text-xs font-semibold text-[#F5EFE5]">FastAPI API</div>
              <div className="text-[11px] text-[#8F8579] mt-1">Hosted on Railway</div>
            </div>
            <div className="p-5 rounded-xl bg-[#100F0D] border border-[#40372D] hover:border-[#665744] transition-all">
              <Cpu className="w-6 h-6 text-[#C5A474] mx-auto mb-3" />
              <div className="text-xs font-semibold text-[#F5EFE5]">Redis + Playwright Worker</div>
              <div className="text-[11px] text-[#8F8579] mt-1">Asynchronous RQ queue</div>
            </div>
            <div className="p-5 rounded-xl bg-[#100F0D] border border-[#40372D] hover:border-[#665744] transition-all">
              <Database className="w-6 h-6 text-[#C5A474] mx-auto mb-3" />
              <div className="text-xs font-semibold text-[#F5EFE5]">PostgreSQL VersionArtifact</div>
              <div className="text-[11px] text-[#8F8579] mt-1">Shared image binary storage</div>
            </div>
          </div>
        </div>
      </section>

      {/* =====================================================================
          7. BOTTOM DUAL CHOICE: CONTINUE AS NORMAL USER OR ADMIN
         ===================================================================== */}
      <section id="continue-options" className="py-24 bg-[#100F0D] border-t border-[#40372D]">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-[#211D19] border border-[#C5A474]/30 text-[#C5A474] text-xs font-medium mb-3">
              <Sparkles className="w-3.5 h-3.5 text-[#C5A474]" />
              <span>Choose Your Workspace</span>
            </div>
            <h2 className="font-serif text-3xl sm:text-4xl font-normal text-[#F5EFE5] tracking-tight">
              Ready to Observe the Web in Real-Time?
            </h2>
            <p className="mt-3.5 text-sm text-[#BDB3A7]">
              Continue as a normal evaluator without login credentials, or authenticate to access the administration dashboard.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* OPTION 1: NORMAL USER / JUDGE WORKSPACE */}
            <div className="relative bg-[#211D19] border-2 border-[#C5A474] rounded-3xl shadow-luxury p-8 flex flex-col justify-between hover:border-[#D8BB8E] transition-all duration-200">
              <div className="absolute -top-3.5 left-7 bg-[#C5A474] text-[#141210] text-[11px] font-bold px-3 py-0.5 rounded-full uppercase tracking-wider shadow-sm">
                Recommended for Evaluators
              </div>

              <div>
                <div className="w-12 h-12 rounded-2xl bg-[#342B20] border border-[#C5A474]/40 text-[#C5A474] flex items-center justify-center mb-6">
                  <Compass className="w-6 h-6" />
                </div>
                <h3 className="font-serif text-2xl font-medium text-[#F5EFE5]">Normal User Workspace</h3>
                <p className="text-xs text-[#BDB3A7] mt-2.5 leading-relaxed font-sans">
                  Monitor any public website, trigger genuine Playwright captures, and inspect verified diffs.
                  No login credentials, Google account, or invitation required.
                </p>

                <ul className="mt-6 space-y-3 text-xs text-[#BDB3A7]">
                  <li className="flex items-center space-x-2.5">
                    <CheckCircle2 className="w-4 h-4 text-[#34C59A] shrink-0" />
                    <span>Instant anonymous evaluation session</span>
                  </li>
                  <li className="flex items-center space-x-2.5">
                    <CheckCircle2 className="w-4 h-4 text-[#34C59A] shrink-0" />
                    <span>Real background worker checks and captures</span>
                  </li>
                  <li className="flex items-center space-x-2.5">
                    <CheckCircle2 className="w-4 h-4 text-[#34C59A] shrink-0" />
                    <span>Side-by-side & visual overlay screenshot diffs</span>
                  </li>
                  <li className="flex items-center space-x-2.5">
                    <CheckCircle2 className="w-4 h-4 text-[#34C59A] shrink-0" />
                    <span>Interactive CSS region picker rules</span>
                  </li>
                </ul>
              </div>

              <div className="mt-8 pt-6 border-t border-[#40372D]">
                <button
                  onClick={onEnterNormalUser}
                  className="w-full py-3.5 px-6 bg-[#C5A474] hover:bg-[#D8BB8E] text-[#141210] font-semibold text-sm rounded-xl shadow-gold transition-all flex items-center justify-center space-x-2 group"
                >
                  <span>Continue as Normal User</span>
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </button>
                <div className="text-center mt-2.5 text-[11px] text-[#8F8579]">
                  Opens interactive evaluation workspace immediately
                </div>
              </div>
            </div>

            {/* OPTION 2: ADMIN LOGIN */}
            <div className="bg-[#211D19] border border-[#40372D] rounded-3xl shadow-sm p-8 flex flex-col justify-between hover:border-[#665744] transition-all duration-200">
              <div>
                <div className="w-12 h-12 rounded-2xl bg-[#141210] border border-[#40372D] text-[#C5A474] flex items-center justify-center mb-6">
                  <Lock className="w-6 h-6" />
                </div>
                <h3 className="font-serif text-2xl font-medium text-[#F5EFE5]">Admin Console</h3>
                <p className="text-xs text-[#BDB3A7] mt-2.5 leading-relaxed font-sans">
                  Protected administrative console for configuring encrypted notification channels, managing global system monitors, and viewing backend logs.
                </p>

                {loginError && (
                  <div className="mt-4 p-3 bg-[#ED7777]/10 border border-[#ED7777]/30 text-[#ED7777] text-xs rounded-xl flex items-center space-x-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{loginError}</span>
                  </div>
                )}

                <form onSubmit={handleBottomAdminSubmit} className="mt-6 space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-[#BDB3A7] mb-1.5 font-sans">
                      Administrative Password
                    </label>
                    <input
                      type="password"
                      placeholder="Enter admin password..."
                      value={bottomAdminPassword}
                      onChange={(e) => setBottomAdminPassword(e.target.value)}
                      className="w-full text-sm px-3.5 py-2.5 bg-[#141210] border border-[#40372D] rounded-xl text-[#F5EFE5] placeholder-[#8F8579] focus:outline-none focus:ring-1 focus:ring-[#C5A474] focus:border-[#C5A474] transition-all font-sans"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={loginLoading || !bottomAdminPassword.trim()}
                    className="w-full py-3.5 px-6 bg-[#2A2520] hover:bg-[#342B20] border border-[#40372D] hover:border-[#665744] disabled:opacity-50 text-[#F5EFE5] font-semibold text-sm rounded-xl shadow-sm transition-all flex items-center justify-center space-x-2"
                  >
                    {loginLoading ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin text-[#C5A474]" />
                        <span>Verifying...</span>
                      </>
                    ) : (
                      <>
                        <Key className="w-4 h-4 text-[#C5A474]" />
                        <span>Continue as Admin</span>
                      </>
                    )}
                  </button>
                </form>
              </div>

              <div className="mt-8 pt-6 border-t border-[#40372D] flex items-center justify-between text-[11px] text-[#8F8579]">
                <span>Access: Restricted</span>
                <span>Production Observability Platform</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =====================================================================
          8. FOOTER
         ===================================================================== */}
      <footer className="border-t border-[#40372D] bg-[#100F0D] py-8 text-center text-xs text-[#8F8579]">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-2">
            <Globe className="w-4 h-4 text-[#C5A474]" />
            <span className="font-serif font-medium text-[#F5EFE5]">Website Change Detector</span>
            <span>&bull;</span>
            <span>Distributed Production Pipeline</span>
          </div>
          <div>
            FastAPI Backend on Railway &bull; React Frontend on Vercel &bull; Playwright Engine
          </div>
        </div>
      </footer>

      {/* =====================================================================
          9. NAVBAR "CONTINUE" MODAL (ROLE SELECTOR)
         ===================================================================== */}
      {isContinueModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#141210]/80 backdrop-blur-md p-4 animate-fade-in">
          <div className="bg-[#211D19] rounded-3xl shadow-luxury max-w-xl w-full p-8 border border-[#40372D] relative text-left">
            <button
              onClick={() => setIsContinueModalOpen(false)}
              className="absolute top-5 right-5 text-[#8F8579] hover:text-[#F5EFE5] p-1.5 rounded-lg hover:bg-[#2A2520] transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="text-left mb-6">
              <div className="inline-flex items-center space-x-1.5 text-xs font-semibold text-[#C5A474] bg-[#342B20] border border-[#C5A474]/30 px-2.5 py-1 rounded-full mb-3">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Select Experience</span>
              </div>
              <h3 className="font-serif text-2xl font-normal text-[#F5EFE5]">Continue to Website Change Detector</h3>
              <p className="text-xs text-[#BDB3A7] mt-1.5 font-sans">
                Choose whether you would like to enter the interactive public workspace or access the admin console.
              </p>
            </div>

            <div className="space-y-4">
              {/* Option 1: Normal User / Judge */}
              <div
                onClick={() => {
                  setIsContinueModalOpen(false);
                  onEnterNormalUser();
                }}
                className="p-5 rounded-2xl border-2 border-[#C5A474] bg-[#342B20]/40 hover:bg-[#342B20]/70 cursor-pointer transition-all flex items-start space-x-4 group"
              >
                <div className="w-10 h-10 rounded-xl bg-[#C5A474] text-[#141210] flex items-center justify-center shrink-0 shadow-sm">
                  <Compass className="w-5 h-5" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="font-serif font-medium text-base text-[#F5EFE5]">Normal User Workspace</span>
                    <span className="text-[10px] bg-[#C5A474]/20 text-[#C5A474] border border-[#C5A474]/30 font-semibold px-2 py-0.5 rounded-full">
                      No Login Required
                    </span>
                  </div>
                  <p className="text-xs text-[#BDB3A7] mt-1.5 leading-relaxed font-sans">
                    Instantly monitor any public website, trigger automated browser checks, and view side-by-side & overlay diffs.
                  </p>
                  <div className="mt-3 inline-flex items-center space-x-1 text-xs font-semibold text-[#C5A474] group-hover:translate-x-1 transition-transform">
                    <span>Enter as Normal User</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </div>
                </div>
              </div>

              {/* Option 2: Admin Login */}
              <div className="p-5 rounded-2xl border border-[#40372D] bg-[#141210] hover:border-[#665744] transition-all">
                <div className="flex items-start space-x-4">
                  <div className="w-10 h-10 rounded-xl bg-[#211D19] border border-[#40372D] text-[#C5A474] flex items-center justify-center shrink-0">
                    <Lock className="w-5 h-5" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span className="font-serif font-medium text-base text-[#F5EFE5]">Admin Console</span>
                      <span className="text-[10px] bg-[#211D19] text-[#8F8579] border border-[#40372D] font-semibold px-2 py-0.5 rounded-full">
                        Password Protected
                      </span>
                    </div>
                    <p className="text-xs text-[#BDB3A7] mt-1.5 leading-relaxed font-sans">
                      Manage encrypted notification credentials (Discord, Telegram, SMTP), system-wide monitors, and logs.
                    </p>

                    <form onSubmit={handleModalAdminSubmit} className="mt-3.5 flex items-center space-x-2">
                      <input
                        type="password"
                        placeholder="Admin password..."
                        value={adminPassword}
                        onChange={(e) => setAdminPassword(e.target.value)}
                        className="flex-1 text-xs px-3 py-2 bg-[#1A1714] border border-[#40372D] rounded-lg text-[#F5EFE5] placeholder-[#8F8579] focus:outline-none focus:ring-1 focus:ring-[#C5A474]"
                      />
                      <button
                        type="submit"
                        disabled={loginLoading || !adminPassword.trim()}
                        className="px-4 py-2 bg-[#C5A474] hover:bg-[#D8BB8E] disabled:opacity-50 text-[#141210] text-xs font-semibold rounded-lg shadow-sm transition-all"
                      >
                        {loginLoading ? 'Checking...' : 'Sign In'}
                      </button>
                    </form>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LandingPage;
