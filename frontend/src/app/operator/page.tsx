import DashboardPage from "@/components/dashboard/DashboardPage";

export default function OperatorDashboard() {
  return (
    <DashboardPage
      role="operator"
      comingSoon={[
        { title: "Check in a bag", description: "Scan an arriving bag at the warehouse." },
        { title: "Photograph contents", description: "Upload a photo for Gemini to classify." },
        { title: "Review classifications", description: "Confirm or correct detected items." },
      ]}
    />
  );
}
