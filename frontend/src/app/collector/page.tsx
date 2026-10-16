import DashboardPage from "@/components/dashboard/DashboardPage";

export default function CollectorDashboard() {
  return (
    <DashboardPage
      role="collector"
      comingSoon={[
        { title: "Today's route", description: "Pickups assigned to you, in order." },
        { title: "Scan a bag", description: "Scan the bag's QR code to mark it collected." },
        { title: "History", description: "Bags you've collected this week." },
      ]}
    />
  );
}
