"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import DemoSignIn from "@/components/auth/DemoSignIn";
import Logo from "@/components/ui/Logo";
import { dashboardPath, type Role } from "@/lib/roles";

import styles from "./landing.module.css";

const GITHUB = "https://github.com/saadhiq/EcoTrace";

const icon = (d: ReactNode) => (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
       strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {d}
  </svg>
);

const STEPS = [
  {
    title: "Schedule a pickup",
    text: "The resident picks a date and the QR-coded bags to collect.",
    icon: icon(<><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18M8 14h3" /></>),
  },
  {
    title: "Collector scans the bag",
    text: "Each bag's QR code is scanned with the phone camera, at the door and again at the warehouse.",
    icon: icon(<><path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3" /><path d="M8 9h3v3H8zM13 13h3v3h-3zM13 9h3M8 15h2" /></>),
  },
  {
    title: "Gemini identifies the items",
    text: "An operator photographs the contents; Gemini lists every item by category, then a person reviews it.",
    icon: icon(<><path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z" /><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z" /></>),
  },
  {
    title: "Eco score, tips and swaps",
    text: "The household sees what it throws away, practical tips in English, Sinhala or Tamil, and greener swaps.",
    icon: icon(<><path d="M5 19c0-8 5-13 14-14-1 9-6 14-14 14z" /><path d="M5 19l6-6" /></>),
  },
];

const ROLE_PREVIEW: Record<Role, string> = {
  resident: "A household with QR-coded bags, an upcoming pickup, eco score, Gemini tips and sustainable swaps.",
  collector: "A pickup to collect today: accept it, simulate the QR scans, complete and hand over at the warehouse.",
  operator: "A bag waiting in the warehouse queue: use a sample photo and watch Gemini list the items.",
  admin: "Overview, AI quality, pickup timelines and partners (read-only for accounts and partners).",
};

const GEMINI_POINTS = [
  {
    title: "Structured output",
    text: "Gemini answers in a fixed JSON schema: item, category from our taxonomy, material, quantity, confidence and hazard flags. Nothing is free text.",
  },
  {
    title: "Human review",
    text: "The result is a draft. The operator edits or confirms every item, and we keep both Gemini's answer and the final list.",
  },
  {
    title: "Manual fallback",
    text: "If Gemini is slow or unavailable, the page switches to manual entry, so the warehouse never stops.",
  },
];

const CLOUD = [
  { label: "Firebase", text: "Hosting serves this app; Firebase Auth signs people in, with each person's role stored as a custom claim." },
  { label: "Firestore", text: "Households, bags, pickups and results. Screens update live, and security rules let people read only their own data." },
  { label: "Cloud Run", text: "The FastAPI backend: verifies every request, runs one state machine for pickups and bags, and serves the partner API." },
  { label: "Gemini on Vertex AI", text: "Classifies bag photos, writes multilingual tips from aggregates, and ranks swaps from a partner catalog." },
];

const PRIVACY = [
  { title: "Opt-in consent", text: "Data sharing is off until the resident turns it on, with a plain-language explanation. Every change is logged." },
  { title: "Groups of 5+ only", text: "Partners never see a household. They only get anonymised segments of at least 5 consenting households." },
  { title: "Photos deleted after 30 days", text: "Bag photos sit in a private bucket that deletes them automatically after 30 days." },
];

/** Public landing page at "/". Signed-in visitors see it too, with a link to their dashboard. */
export default function Landing() {
  const { state } = useAuth();
  const signedIn = state.status === "ready";
  const dashboard = signedIn ? dashboardPath(state.profile.role) : "/login";

  const dashboardButton = (
    <Link className={styles.primary} href={dashboard} data-testid="go-dashboard">
      Go to my dashboard
    </Link>
  );

  return (
    <div className={styles.page} data-testid="landing">
      <header className={styles.topbar}>
        <div className={styles.topbarInner}>
          <Logo />
          {signedIn ? (
            <Link className={`${styles.secondary} ${styles.small}`} href={dashboard}>
              My dashboard
            </Link>
          ) : (
            <Link className={`${styles.secondary} ${styles.small}`} href="/login">
              Sign in
            </Link>
          )}
        </div>
      </header>

      <main>
        <section className={styles.hero}>
          <div className={styles.heroInner}>
            <span className={styles.eyebrow}>EcoTrace</span>
            <h1 className={styles.headline}>Know what every household throws away</h1>
            <p className={styles.lede}>
              QR-coded bags, phone scanning and Gemini turn household waste into data that helps people recycle more.
            </p>
            <div className={styles.actions}>
              {signedIn ? (
                dashboardButton
              ) : (
                <>
                  <a className={styles.primary} href="#try" data-testid="try-demo">
                    Try the live demo
                  </a>
                  <Link className={styles.secondary} href="/login">
                    Sign in
                  </Link>
                </>
              )}
            </div>
          </div>
        </section>

        <section className={styles.section} aria-labelledby="how">
          <div className={styles.sectionInner}>
            <div>
              <h2 id="how" className={styles.h2}>How it works</h2>
              <p className={styles.sub}>Every bag is traceable from the doorstep to the warehouse.</p>
            </div>
            <ol className={styles.steps}>
              {STEPS.map((s, i) => (
                <li key={s.title} className={styles.step}>
                  <span className={styles.icon}>{s.icon}</span>
                  <div>
                    <div className={styles.stepNum}>Step {i + 1}</div>
                    <div className={styles.stepTitle}>{s.title}</div>
                    <p className={styles.stepText}>{s.text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="try" className={styles.sectionAlt} aria-labelledby="try-title">
          <div className={styles.sectionInner}>
            <div>
              <h2 id="try-title" className={styles.h2}>Try it in one click</h2>
              <p className={styles.sub}>
                {signedIn
                  ? "You're signed in. Open your dashboard, or sign out from it to try another role."
                  : "No password. Pick a role and you're in. Demo accounts are shared and reset their sample data on every sign-in."}
              </p>
            </div>
            {signedIn ? <div>{dashboardButton}</div> : <DemoSignIn descriptions={ROLE_PREVIEW} />}
          </div>
        </section>

        <section className={styles.section} aria-labelledby="gemini">
          <div className={styles.sectionInner}>
            <div>
              <h2 id="gemini" className={styles.h2}>Gemini at the warehouse</h2>
              <p className={styles.sub}>A real result from the operator screen: one photo of a bag, every item listed.</p>
            </div>
            <div className={styles.split}>
              <figure>
                {/* eslint-disable-next-line @next/next/no-img-element -- static export, pre-optimised WebP */}
                <img
                  className={styles.shot}
                  src="/landing/gemini-results.webp"
                  width={1080}
                  height={720}
                  loading="lazy"
                  decoding="async"
                  alt="EcoTrace operator screen: a bag photo next to Gemini's item list (a beer can and plastic bottles, each with category, material and confidence)"
                />
                <figcaption className={styles.caption}>Operator screen in the live app (gemini-3.5-flash).</figcaption>
              </figure>
              <ul className={styles.points}>
                {GEMINI_POINTS.map((p) => (
                  <li key={p.title} className={styles.point}>
                    <div className={styles.pointTitle}>{p.title}</div>
                    <p className={styles.pointText}>{p.text}</p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <section className={styles.sectionAlt} aria-labelledby="cloud">
          <div className={styles.sectionInner}>
            <div>
              <h2 id="cloud" className={styles.h2}>Built on Google Cloud</h2>
              <p className={styles.sub}>Everything runs in the asia-south1 region.</p>
            </div>
            <div className={styles.tiles}>
              {CLOUD.map((c) => (
                <div key={c.label} className={styles.tile}>
                  <span className={styles.tileLabel}>{c.label}</span>
                  <p className={styles.tileText}>{c.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className={styles.section} aria-labelledby="privacy">
          <div className={styles.sectionInner}>
            <h2 id="privacy" className={styles.h2}>Privacy by design</h2>
            <div className={styles.privacy}>
              {PRIVACY.map((p) => (
                <div key={p.title} className={styles.privacyItem}>
                  <span className={styles.icon}>
                    {icon(<><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></>)}
                  </span>
                  <div>
                    <div className={styles.stepTitle}>{p.title}</div>
                    <p className={styles.stepText}>{p.text}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>

      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <span>
            Team <strong>SinBotics</strong> · Built for the Google Cloud AI Builder Cup
          </span>
          <a href={GITHUB} target="_blank" rel="noopener noreferrer">
            GitHub: saadhiq/EcoTrace
          </a>
        </div>
      </footer>
    </div>
  );
}
