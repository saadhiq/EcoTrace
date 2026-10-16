import Spinner from "./Spinner";
import styles from "./ui.module.css";

export default function FullPageSpinner() {
  return (
    <div className={styles.fullPage}>
      <Spinner size={32} />
    </div>
  );
}
