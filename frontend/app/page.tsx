"use client";

/**
 * app/page.tsx – Landing / connect page.
 *
 * On load: silently checks if the user is already authenticated.
 *   → Authenticated  : redirect to /dashboard
 *   → Not authenticated: show the "Connect Gmail" landing page
 *
 * The "Connect Gmail" button does a full browser navigation to the backend
 * OAuth endpoint (NOT an axios call) because the OAuth flow is a redirect chain.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authApi, is401 } from "@/lib/api";
import { Package, Mail, ShieldCheck, BarChart2, Loader2 } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function LandingPage() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);
  const [connectError, setConnectError] = useState<string | null>(null);

  // ── On mount: check if already logged in ──────────────────────────────────
  useEffect(() => {
    authApi
      .me()
      .then(() => {
        router.replace("/dashboard");
      })
      .catch((err) => {
        if (is401(err)) {
          setChecking(false);
        } else {
          setChecking(false);
        }
      });
  }, [router]);

  // ── Read error param from URL (e.g. ?error=access_denied) ─────────────────
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const err = params.get("error");
    if (err) {
      const messages: Record<string, string> = {
        access_denied: "Google sign-in was cancelled. Please try again.",
        state_mismatch: "Security check failed. Please try again.",
        token_exchange_failed: "Could not connect to Google. Please try again.",
        userinfo_failed: "Could not fetch your Google account info. Please try again.",
        no_email: "No email address found in your Google account.",
      };
      setConnectError(messages[err] ?? "Something went wrong. Please try again.");
      setChecking(false);
    }
  }, []);

  const handleConnect = () => {
    // Full browser navigation required for the OAuth redirect chain
    window.location.href = `${API_URL}/auth/google`;
  };

  // ── Loading state while checking auth ─────────────────────────────────────
  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950">
        <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
      </div>
    );
  }

  // ── Landing page ──────────────────────────────────────────────────────────
  return (
    <main className="min-h-screen bg-slate-950 text-white flex flex-col">
      {/* Nav */}
      <nav className="px-6 py-4 flex items-center gap-3 border-b border-slate-800">
        <Package className="w-6 h-6 text-blue-400" />
        <span className="font-semibold text-lg tracking-tight">
          PackageTracker AI
        </span>
      </nav>

      {/* Hero */}
      <section className="flex-1 flex flex-col items-center justify-center text-center px-6 py-20 gap-8">
        <div className="flex items-center justify-center w-20 h-20 rounded-2xl bg-blue-500/10 border border-blue-500/20">
          <Package className="w-10 h-10 text-blue-400" />
        </div>

        <div className="max-w-2xl space-y-4">
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight">
            All your packages,{" "}
            <span className="text-blue-400">one place</span>
          </h1>
          <p className="text-slate-400 text-lg sm:text-xl leading-relaxed">
            Connect your Gmail and let AI automatically find, track, and
            organise every order and shipment — no copy-pasting tracking
            numbers ever again.
          </p>
        </div>

        {/* Error banner */}
        {connectError && (
          <div className="w-full max-w-md bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 text-red-400 text-sm">
            {connectError}
          </div>
        )}

        {/* CTA button */}
        <button
          onClick={handleConnect}
          className="flex items-center gap-3 px-8 py-4 bg-blue-600 hover:bg-blue-500
                     active:bg-blue-700 text-white font-semibold rounded-xl
                     transition-all duration-150 shadow-lg shadow-blue-600/30
                     hover:shadow-blue-500/40 text-lg"
        >
          {/* Google "G" SVG logo */}
          <svg className="w-5 h-5" viewBox="0 0 24 24" aria-hidden="true">
            <path
              fill="currentColor"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="currentColor"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="currentColor"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="currentColor"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          Connect Gmail
        </button>

        <p className="text-slate-500 text-sm max-w-xs">
          Read-only access. We never send emails on your behalf.
        </p>
      </section>

      {/* Feature grid */}
      <section className="px-6 pb-20">
        <div className="max-w-3xl mx-auto grid sm:grid-cols-3 gap-4">
          <FeatureCard
            icon={<Mail className="w-5 h-5 text-blue-400" />}
            title="Gmail integration"
            description="Reads order, shipping, and delivery emails automatically."
          />
          <FeatureCard
            icon={<ShieldCheck className="w-5 h-5 text-emerald-400" />}
            title="Private & secure"
            description="Read-only Gmail scope. Email bodies are never stored."
          />
          <FeatureCard
            icon={<BarChart2 className="w-5 h-5 text-violet-400" />}
            title="Spend insights"
            description="See your orders by vendor and track delivery timelines."
          />
        </div>
      </section>

      {/* Footer */}
      <footer className="text-center text-slate-600 text-xs py-6 border-t border-slate-800">
        PackageTracker AI · Built with Claude
      </footer>
    </main>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 space-y-2">
      <div className="flex items-center gap-2">
        {icon}
        <h3 className="font-semibold text-sm text-slate-100">{title}</h3>
      </div>
      <p className="text-slate-400 text-sm leading-relaxed">{description}</p>
    </div>
  );
}
