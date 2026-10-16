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
    <div className="min-h-screen bg-[#F5F7FB] text-[#101828] font-sans flex flex-col selection:bg-blue-100 selection:text-blue-900">
      {/* =====================================================================
          1. STICKY TOP NAVBAR
         ===================================================================== */}
      <header className="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-[#E2E8F0] transition-all">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo & Brand */}
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
              <Globe className="w-5 h-5" />
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-base leading-tight tracking-tight text-[#101828]">
                Website Change Detector
              </span>
              <span className="text-[10px] text-[#66758C] font-semibold tracking-wider uppercase">
                Autonomous Observability
              </span>
            </div>
          </div>

          {/* Center Navigation Links */}
          <nav className="hidden md:flex items-center space-x-7 text-xs font-semibold text-[#66758C]">
            <button
              onClick={() => scrollToSection('features')}
              className="hover:text-blue-600 transition-colors"
            >
              Features
            </button>
            <button
              onClick={() => scrollToSection('how-it-works')}
              className="hover:text-blue-600 transition-colors"
            >
              How It Works
            </button>
            <button
              onClick={() => scrollToSection('preview')}
              className="hover:text-blue-600 transition-colors"
            >
              Live Diff Engine
            </button>
            <button
              onClick={() => scrollToSection('architecture')}
              className="hover:text-blue-600 transition-colors"
            >
              Architecture
            </button>
            <button
              onClick={() => scrollToSection('continue-options')}
              className="hover:text-blue-600 transition-colors"
            >
              Get Started
            </button>
          </nav>

          {/* Right Action Buttons */}
          <div className="flex items-center space-x-3">
            {/* System Status Pill */}
            <div className="hidden lg:flex items-center space-x-2 text-[11px] bg-slate-50 border border-slate-200 px-2.5 py-1 rounded-full text-[#66758C]">
              <span
                className={`w-2 h-2 rounded-full ${
                  health?.status === 'ok' ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'
                }`}
              />
              <span className="font-medium">
                {healthLoading ? 'Connecting...' : health?.status === 'ok' ? 'System Online' : 'Checking'}
              </span>
            </div>

            {/* Direct Admin Login Quick-Action */}
            <button
              onClick={() => scrollToSection('continue-options')}
              className="hidden sm:inline-flex items-center space-x-1.5 text-xs font-semibold text-[#475569] hover:text-[#101828] px-3 py-2 rounded-lg hover:bg-slate-100 transition-colors"
            >
              <Lock className="w-3.5 h-3.5" />
              <span>Admin Login</span>
            </button>

            {/* Primary Continue Button */}
            <button
              onClick={() => setIsContinueModalOpen(true)}
              className="inline-flex items-center space-x-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white text-xs font-semibold px-4 py-2 rounded-xl shadow-sm shadow-blue-500/25 transition-all transform active:scale-95"
            >
              <span>Continue</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </header>

      {/* =====================================================================
          2. HERO SECTION
         ===================================================================== */}
      <section className="relative pt-16 pb-20 overflow-hidden">
        {/* Subtle background glow */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-96 bg-gradient-to-b from-blue-50/60 to-transparent pointer-events-none -z-10" />

        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          {/* Eyebrow badge */}
          <div className="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-full bg-blue-50 border border-blue-200/80 text-blue-700 text-xs font-semibold mb-6 shadow-xs animate-fade-in">
            <Sparkles className="w-3.5 h-3.5 text-blue-600" />
            <span>Real Headless Chromium Captures & SHA-256 Content Diffing</span>
          </div>

          {/* Main Headline */}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-[#101828] tracking-tight leading-[1.15] max-w-4xl mx-auto">
            Detect Every Website Change.{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 via-indigo-600 to-violet-600">
              Down to the Pixel and Word.
            </span>
          </h1>

          {/* Subtitle */}
          <p className="mt-5 text-base sm:text-lg text-[#66758C] max-w-2xl mx-auto leading-relaxed">
            Autonomous web page monitoring powered by Playwright headless browsers, normalized text extraction,
            and cryptographic hash validation. Zero false positives from dynamic tracking scripts or ad noise.
          </p>

          {/* CTA Group */}
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3.5">
            {/* Primary Continue Button */}
            <button
              onClick={() => setIsContinueModalOpen(true)}
              className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-6 py-3.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm rounded-xl shadow-lg shadow-blue-600/25 transition-all transform hover:-translate-y-0.5 active:translate-y-0"
            >
              <span>Continue to Platform</span>
              <ArrowRight className="w-4 h-4" />
            </button>

            {/* Direct Judge Workspace Button (Recommended for evaluators) */}
            <button
              onClick={onEnterNormalUser}
              className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-6 py-3.5 bg-white hover:bg-slate-50 text-[#101828] font-semibold text-sm rounded-xl border border-slate-200 shadow-xs hover:border-slate-300 transition-all"
            >
              <Compass className="w-4 h-4 text-blue-600" />
              <span>Explore Judge Workspace</span>
              <span className="text-[11px] font-normal text-[#66758C]">(No Login)</span>
            </button>
          </div>

          {/* Feature highlights below CTA */}
          <div className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-[#66758C]">
            <span className="flex items-center space-x-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>No login required for normal users</span>
            </span>
            <span className="flex items-center space-x-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Automated Playwright Chromium snapshots</span>
            </span>
            <span className="flex items-center space-x-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Side-by-side & overlay visual diffs</span>
            </span>
          </div>

          {/* =====================================================================
              HERO VISUAL PREVIEW MOCKUP
             ===================================================================== */}
          <div id="preview" className="mt-14 max-w-4xl mx-auto rounded-2xl bg-white border border-[#E2E8F0] shadow-xl overflow-hidden transition-all">
            {/* Mockup browser chrome top bar */}
            <div className="bg-slate-100/90 border-b border-[#E2E8F0] px-4 py-2.5 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <span className="w-3 h-3 rounded-full bg-rose-400" />
                <span className="w-3 h-3 rounded-full bg-amber-400" />
                <span className="w-3 h-3 rounded-full bg-emerald-400" />
              </div>
              <div className="bg-white border border-slate-200 px-4 py-1 rounded-md text-[11px] font-mono text-[#66758C] flex items-center space-x-2 w-72 justify-center shadow-xs">
                <Globe className="w-3 h-3 text-slate-400" />
                <span className="truncate">https://store.example.com/item/pro-15</span>
              </div>
              <div className="flex items-center space-x-2 text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                <span>CHANGED DETECTED</span>
              </div>
            </div>

            {/* Mockup comparison body */}
            <div className="p-6 bg-slate-50/50">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Version 1 Card */}
                <div className="bg-white border border-slate-200 rounded-xl p-4 text-left shadow-xs">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                    <span className="text-xs font-bold text-slate-700">Baseline Version (v1)</span>
                    <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono">10:00 AM</span>
                  </div>
                  <div className="mt-3 space-y-2">
                    <div className="text-xs font-medium text-slate-800">Ultra-Lightweight Developer Laptop 15"</div>
                    <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100 text-xs">
                      <div className="text-[#66758C] line-through">Stock: In Stock (42 units)</div>
                      <div className="text-base font-bold text-slate-900 mt-1">$1,299.00 USD</div>
                    </div>
                  </div>
                </div>

                {/* Version 2 Card (Changed) */}
                <div className="bg-white border-2 border-blue-500 rounded-xl p-4 text-left shadow-md relative">
                  <div className="absolute -top-2.5 right-4 bg-blue-600 text-white text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">
                    Difference Verified
                  </div>
                  <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                    <span className="text-xs font-bold text-blue-700">Captured Snapshot (v2)</span>
                    <span className="text-[10px] bg-blue-50 text-blue-700 px-2 py-0.5 rounded font-mono">10:15 AM</span>
                  </div>
                  <div className="mt-3 space-y-2">
                    <div className="text-xs font-medium text-slate-800">Ultra-Lightweight Developer Laptop 15"</div>
                    <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-emerald-700 font-semibold">Price Drop Detected (-23%)</span>
                        <span className="text-rose-600 line-through text-[11px]">$1,299.00</span>
                      </div>
                      <div className="text-lg font-bold text-emerald-800 mt-0.5">$999.00 USD</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Verified Text Diff Chip Strip */}
              <div className="mt-4 p-3 bg-white border border-slate-200 rounded-xl flex flex-wrap items-center justify-between gap-2 text-xs">
                <div className="flex items-center space-x-2">
                  <span className="text-[#66758C] font-medium">Text Delta:</span>
                  <span className="px-2 py-0.5 bg-rose-50 text-rose-700 border border-rose-200 rounded font-mono text-[11px] line-through">
                    - $1,299.00
                  </span>
                  <span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded font-mono text-[11px] font-semibold">
                    + $999.00
                  </span>
                </div>
                <div className="text-[11px] text-[#66758C] font-mono">
                  SHA-256: <span className="text-slate-800 font-semibold">e4b7...910a</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* =====================================================================
          3. METRICS / STATS STRIP
         ===================================================================== */}
      <section className="border-y border-[#E2E8F0] bg-white py-8">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
          <div>
            <div className="text-2xl sm:text-3xl font-extrabold text-[#101828]">0% Noise</div>
            <div className="text-xs text-[#66758C] mt-1 font-medium">Tracking script & telemetry exclusion</div>
          </div>
          <div>
            <div className="text-2xl sm:text-3xl font-extrabold text-[#101828]">Playwright</div>
            <div className="text-xs text-[#66758C] mt-1 font-medium">Headless Chromium full-viewport captures</div>
          </div>
          <div>
            <div className="text-2xl sm:text-3xl font-extrabold text-[#101828]">SHA-256</div>
            <div className="text-xs text-[#66758C] mt-1 font-medium">Normalized cryptographic content hashing</div>
          </div>
          <div>
            <div className="text-2xl sm:text-3xl font-extrabold text-[#101828]">PostgreSQL</div>
            <div className="text-xs text-[#66758C] mt-1 font-medium">VersionArtifact distributed binary persistence</div>
          </div>
        </div>
      </section>

      {/* =====================================================================
          4. CORE FEATURES SECTION
         ===================================================================== */}
      <section id="features" className="py-20 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto mb-14">
          <div className="text-xs font-bold uppercase tracking-wider text-blue-600 mb-2">Capabilities</div>
          <h2 className="text-3xl font-bold text-[#101828] tracking-tight">
            Engineered for Precision Observability
          </h2>
          <p className="mt-3 text-sm text-[#66758C] leading-relaxed">
            Eliminate noisy alerts and false alarms. Inspect verified visual differences and human-readable text modifications.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1 */}
          <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-xs hover:shadow-md transition-all">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mb-4">
              <Cpu className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-[#101828]">Real Headless Chromium Engine</h3>
            <p className="text-xs text-[#66758C] mt-2 leading-relaxed">
              Executes client-side JavaScript, handles dynamic single-page applications, and captures full-resolution viewport snapshots using Playwright.
            </p>
          </div>

          {/* Card 2 */}
          <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-xs hover:shadow-md transition-all">
            <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center mb-4">
              <Eye className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-[#101828]">Noise & Telemetry Exclusion</h3>
            <p className="text-xs text-[#66758C] mt-2 leading-relaxed">
              Intelligent DOM parsing strips ad trackers, request IDs, cache tokens, and ephemeral configuration variables before diff calculation.
            </p>
          </div>

          {/* Card 3 */}
          <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-xs hover:shadow-md transition-all">
            <div className="w-10 h-10 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center mb-4">
              <Layers className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-[#101828]">Side-by-Side & Overlay Diff</h3>
            <p className="text-xs text-[#66758C] mt-2 leading-relaxed">
              Compare versions visually with interactive slider overlays or inspect word-by-word additions and deletions in human-readable color blocks.
            </p>
          </div>

          {/* Card 4 */}
          <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-xs hover:shadow-md transition-all">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center mb-4">
              <Sliders className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-[#101828]">Visual CSS Region Picker</h3>
            <p className="text-xs text-[#66758C] mt-2 leading-relaxed">
              Visually highlight and click on elements to generate WATCH or IGNORE CSS selectors. Suppress noisy headers or isolate prices with ease.
            </p>
          </div>

          {/* Card 5 */}
          <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-xs hover:shadow-md transition-all">
            <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center mb-4">
              <Bell className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-[#101828]">Encrypted Notifications</h3>
            <p className="text-xs text-[#66758C] mt-2 leading-relaxed">
              Dispatch confirmed change events directly to Discord webhooks, Telegram bots, or SMTP mailboxes with credentials encrypted at rest with Fernet.
            </p>
          </div>

          {/* Card 6 */}
          <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 shadow-xs hover:shadow-md transition-all">
            <div className="w-10 h-10 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center mb-4">
              <Shield className="w-5 h-5" />
            </div>
            <h3 className="text-base font-bold text-[#101828]">Enterprise SSRF & Quota Defenses</h3>
            <p className="text-xs text-[#66758C] mt-2 leading-relaxed">
              Strict destination validation rejects loopbacks, cloud metadata (169.254.169.254), private ranges, and non-standard ports to protect infrastructure.
            </p>
          </div>
        </div>
      </section>

      {/* =====================================================================
          5. HOW IT WORKS 3-STEP SECTION
         ===================================================================== */}
      <section id="how-it-works" className="py-20 bg-slate-100/60 border-y border-[#E2E8F0]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <div className="text-xs font-bold uppercase tracking-wider text-blue-600 mb-2">Workflow</div>
            <h2 className="text-3xl font-bold text-[#101828] tracking-tight">
              Three Steps from URL to Verified Change
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
            {/* Step 1 */}
            <div className="bg-white border border-slate-200 rounded-2xl p-7 shadow-xs relative">
              <div className="w-9 h-9 rounded-full bg-blue-600 text-white font-bold text-sm flex items-center justify-center mb-4">
                1
              </div>
              <h3 className="text-base font-bold text-[#101828]">Add Target URL</h3>
              <p className="text-xs text-[#66758C] mt-2 leading-relaxed">
                Enter any publicly reachable HTTP/HTTPS website. Configure desired check frequency and optional custom region selectors.
              </p>
            </div>

            {/* Step 2 */}
            <div className="bg-white border border-slate-200 rounded-2xl p-7 shadow-xs relative">
              <div className="w-9 h-9 rounded-full bg-indigo-600 text-white font-bold text-sm flex items-center justify-center mb-4">
                2
              </div>
              <h3 className="text-base font-bold text-[#101828]">Headless Playwright Capture</h3>
              <p className="text-xs text-[#66758C] mt-2 leading-relaxed">
                Asynchronous Redis workers boot headless Chromium, execute page scripts, store full-viewport screenshot artifacts, and normalize text.
              </p>
            </div>

            {/* Step 3 */}
            <div className="bg-white border border-slate-200 rounded-2xl p-7 shadow-xs relative">
              <div className="w-9 h-9 rounded-full bg-emerald-600 text-white font-bold text-sm flex items-center justify-center mb-4">
                3
              </div>
              <h3 className="text-base font-bold text-[#101828]">Diff & Alert</h3>
              <p className="text-xs text-[#66758C] mt-2 leading-relaxed">
                The engine evaluates cryptographic SHA-256 deltas. If meaningful content changed, version snapshots and visual overlays are generated.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* =====================================================================
          6. ARCHITECTURE SECTION
         ===================================================================== */}
      <section id="architecture" className="py-20 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto mb-12">
          <div className="text-xs font-bold uppercase tracking-wider text-blue-600 mb-2">Distributed Stack</div>
          <h2 className="text-3xl font-bold text-[#101828] tracking-tight">
            Built for Scalability and Reliability
          </h2>
          <p className="mt-3 text-sm text-[#66758C]">
            Separated API, worker, scheduler, and persistent database storage.
          </p>
        </div>

        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-8 shadow-xs">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-center">
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
              <Globe className="w-6 h-6 text-blue-600 mx-auto mb-2" />
              <div className="text-xs font-bold text-slate-800">React + Vite SPA</div>
              <div className="text-[11px] text-[#66758C] mt-1">Hosted on Vercel</div>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
              <Server className="w-6 h-6 text-indigo-600 mx-auto mb-2" />
              <div className="text-xs font-bold text-slate-800">FastAPI API</div>
              <div className="text-[11px] text-[#66758C] mt-1">Hosted on Railway</div>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
              <Cpu className="w-6 h-6 text-violet-600 mx-auto mb-2" />
              <div className="text-xs font-bold text-slate-800">Redis + Playwright Worker</div>
              <div className="text-[11px] text-[#66758C] mt-1">Asynchronous RQ queue</div>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
              <Database className="w-6 h-6 text-emerald-600 mx-auto mb-2" />
              <div className="text-xs font-bold text-slate-800">PostgreSQL VersionArtifact</div>
              <div className="text-[11px] text-[#66758C] mt-1">Shared image binary storage</div>
            </div>
          </div>
        </div>
      </section>

      {/* =====================================================================
          7. BOTTOM DUAL CHOICE: CONTINUE AS NORMAL USER OR ADMIN
         ===================================================================== */}
      <section id="continue-options" className="py-20 bg-gradient-to-b from-white to-slate-100 border-t border-[#E2E8F0]">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-blue-700 text-xs font-semibold mb-3">
              <Sparkles className="w-3 h-3" />
              <span>Choose Your Workspace</span>
            </div>
            <h2 className="text-3xl font-extrabold text-[#101828] tracking-tight">
              Ready to Observe the Web in Real-Time?
            </h2>
            <p className="mt-3 text-sm text-[#66758C]">
              Continue as a normal evaluator without login credentials, or authenticate to access the administration dashboard.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-7">
            {/* OPTION 1: NORMAL USER / JUDGE WORKSPACE */}
            <div className="relative bg-white border-2 border-blue-500 rounded-3xl shadow-xl p-8 flex flex-col justify-between hover:shadow-2xl transition-all">
              <div className="absolute -top-3.5 left-7 bg-blue-600 text-white text-[11px] font-bold px-3 py-0.5 rounded-full uppercase tracking-wider shadow-sm">
                Recommended for Evaluators
              </div>

              <div>
                <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mb-5">
                  <Compass className="w-6 h-6" />
                </div>
                <h3 className="text-2xl font-bold text-[#101828]">Normal User Workspace</h3>
                <p className="text-xs text-[#66758C] mt-2 leading-relaxed">
                  Monitor any public website, trigger genuine Playwright captures, and inspect verified diffs.
                  No login credentials, Google account, or invitation required.
                </p>

                <ul className="mt-6 space-y-3 text-xs text-[#475569]">
                  <li className="flex items-center space-x-2.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>Instant anonymous evaluation session</span>
                  </li>
                  <li className="flex items-center space-x-2.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>Real background worker checks and captures</span>
                  </li>
                  <li className="flex items-center space-x-2.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>Side-by-side & visual overlay screenshot diffs</span>
                  </li>
                  <li className="flex items-center space-x-2.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>Interactive CSS region picker rules</span>
                  </li>
                </ul>
              </div>

              <div className="mt-8 pt-6 border-t border-slate-100">
                <button
                  onClick={onEnterNormalUser}
                  className="w-full py-3.5 px-6 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm rounded-xl shadow-md transition-all flex items-center justify-center space-x-2 group"
                >
                  <span>Continue as Normal User</span>
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </button>
                <div className="text-center mt-2.5 text-[11px] text-[#94A3B8]">
                  Opens interactive evaluation workspace immediately
                </div>
              </div>
            </div>

            {/* OPTION 2: ADMIN LOGIN */}
            <div className="bg-white border border-[#CBD5E1] rounded-3xl shadow-sm p-8 flex flex-col justify-between hover:border-slate-400 transition-all">
              <div>
                <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-700 flex items-center justify-center mb-5">
                  <Lock className="w-6 h-6" />
                </div>
                <h3 className="text-2xl font-bold text-[#101828]">Admin Console</h3>
                <p className="text-xs text-[#66758C] mt-2 leading-relaxed">
                  Protected administrative console for configuring encrypted notification channels, managing global system monitors, and viewing backend logs.
                </p>

                {loginError && (
                  <div className="mt-4 p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-xl flex items-center space-x-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{loginError}</span>
                  </div>
                )}

                <form onSubmit={handleBottomAdminSubmit} className="mt-6 space-y-3.5">
                  <div>
                    <label className="block text-xs font-semibold text-[#475569] mb-1.5">
                      Administrative Password
                    </label>
                    <input
                      type="password"
                      placeholder="Enter admin password..."
                      value={bottomAdminPassword}
                      onChange={(e) => setBottomAdminPassword(e.target.value)}
                      className="w-full text-sm px-3.5 py-2.5 bg-slate-50 border border-[#CBD5E1] rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={loginLoading || !bottomAdminPassword.trim()}
                    className="w-full py-3.5 px-6 bg-[#101828] hover:bg-[#1A233A] disabled:opacity-50 text-white font-semibold text-sm rounded-xl shadow-sm transition-all flex items-center justify-center space-x-2"
                  >
                    {loginLoading ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        <span>Verifying...</span>
                      </>
                    ) : (
                      <>
                        <Key className="w-4 h-4" />
                        <span>Continue as Admin</span>
                      </>
                    )}
                  </button>
                </form>
              </div>

              <div className="mt-8 pt-6 border-t border-slate-100 flex items-center justify-between text-[11px] text-[#94A3B8]">
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
      <footer className="border-t border-[#E2E8F0] bg-white py-8 text-center text-xs text-[#66758C]">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-2">
            <Globe className="w-4 h-4 text-blue-600" />
            <span className="font-semibold text-slate-800">Website Change Detector</span>
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#101828]/60 backdrop-blur-xs p-4 animate-fade-in">
          <div className="bg-white rounded-3xl shadow-2xl max-w-xl w-full p-7 border border-slate-200 relative">
            <button
              onClick={() => setIsContinueModalOpen(false)}
              className="absolute top-5 right-5 text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="text-left mb-6">
              <div className="inline-flex items-center space-x-1.5 text-xs font-semibold text-blue-600 bg-blue-50 px-2.5 py-1 rounded-full mb-2">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Select Experience</span>
              </div>
              <h3 className="text-2xl font-bold text-[#101828]">Continue to Website Change Detector</h3>
              <p className="text-xs text-[#66758C] mt-1">
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
                className="p-5 rounded-2xl border-2 border-blue-500 bg-blue-50/30 hover:bg-blue-50/70 cursor-pointer transition-all flex items-start space-x-4 group"
              >
                <div className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center shrink-0 shadow-sm">
                  <Compass className="w-5 h-5" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm text-[#101828]">Normal User Workspace</span>
                    <span className="text-[10px] bg-blue-100 text-blue-700 font-semibold px-2 py-0.5 rounded-full">
                      No Login Required
                    </span>
                  </div>
                  <p className="text-xs text-[#66758C] mt-1 leading-relaxed">
                    Instantly monitor any public website, trigger automated browser checks, and view side-by-side & overlay diffs.
                  </p>
                  <div className="mt-3 inline-flex items-center space-x-1 text-xs font-semibold text-blue-600 group-hover:translate-x-1 transition-transform">
                    <span>Enter as Normal User</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </div>
                </div>
              </div>

              {/* Option 2: Admin Login */}
              <div className="p-5 rounded-2xl border border-slate-200 bg-white hover:border-slate-300 transition-all">
                <div className="flex items-start space-x-4">
                  <div className="w-10 h-10 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center shrink-0">
                    <Lock className="w-5 h-5" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-sm text-[#101828]">Admin Console</span>
                      <span className="text-[10px] bg-slate-100 text-[#66758C] font-semibold px-2 py-0.5 rounded-full">
                        Password Protected
                      </span>
                    </div>
                    <p className="text-xs text-[#66758C] mt-1 leading-relaxed">
                      Manage encrypted notification credentials (Discord, Telegram, SMTP), system-wide monitors, and logs.
                    </p>

                    <form onSubmit={handleModalAdminSubmit} className="mt-3 flex items-center space-x-2">
                      <input
                        type="password"
                        placeholder="Admin password..."
                        value={adminPassword}
                        onChange={(e) => setAdminPassword(e.target.value)}
                        className="flex-1 text-xs px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                      <button
                        type="submit"
                        disabled={loginLoading || !adminPassword.trim()}
                        className="px-4 py-2 bg-[#101828] hover:bg-[#1A233A] disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition-all"
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
