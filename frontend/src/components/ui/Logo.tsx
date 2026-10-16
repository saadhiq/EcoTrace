import Link from "next/link";

import styles from "./ui.module.css";

export default function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className={styles.logo} aria-label="EcoTrace home">
      <svg
        className={styles.logoMark}
        width="26"
        height="26"
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
      >
        <path
          d="M20 4c-7.5 0-13 3.8-13 10.2 0 1.6.4 3 1.1 4.2C9 15 12 12 16 10c-3.2 2.3-5.6 5.3-6.9 9.3.9.4 1.9.7 3 .7C18.4 20 20 13 20 4Z"
          fill="currentColor"
        />
        <path d="M4 20c1.5-2 3-3.3 5-4.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
      EcoTrace
    </Link>
  );
}
