import styles from "./page.module.css";

export default function Home() {
  return (
    <main className={styles.main}>
      <h1 className={styles.title}>EcoTrace</h1>
      <p className={styles.tagline}>
        Traceable household waste collection — from pickup to classification.
      </p>
      <p className={styles.status}>Coming soon.</p>
    </main>
  );
}
