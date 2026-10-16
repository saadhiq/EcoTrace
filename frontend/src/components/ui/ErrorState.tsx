import Alert from "./Alert";
import Button from "./Button";
import Card from "./Card";
import styles from "./ui.module.css";

type Props = {
  message: string;
  onRetry: () => void;
  onLogout: () => void;
};

export default function ErrorState({ message, onRetry, onLogout }: Props) {
  return (
    <div className={styles.centered}>
      <Card title="Something went wrong" className={styles.errorCard}>
        <Alert>{message}</Alert>
        <div className={styles.row}>
          <Button onClick={onRetry}>Try again</Button>
          <Button variant="secondary" onClick={onLogout}>
            Log out
          </Button>
        </div>
      </Card>
    </div>
  );
}
