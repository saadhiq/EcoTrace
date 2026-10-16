import type { ButtonHTMLAttributes } from "react";

import Spinner from "./Spinner";
import styles from "./ui.module.css";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
  block?: boolean;
  loading?: boolean;
};

export default function Button({
  variant = "primary",
  block = false,
  loading = false,
  className,
  children,
  disabled,
  ...rest
}: Props) {
  const classes = [styles.button, styles[variant], block && styles.block, className]
    .filter(Boolean)
    .join(" ");
  return (
    <button className={classes} disabled={disabled || loading} {...rest}>
      {loading && <Spinner size={16} />}
      {children}
    </button>
  );
}
