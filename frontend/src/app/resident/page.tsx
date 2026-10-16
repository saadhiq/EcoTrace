import DashboardPage from "@/components/dashboard/DashboardPage";

export default function ResidentDashboard() {
  return (
    <DashboardPage
      role="resident"
      comingSoon={[
        { title: "Schedule a pickup", description: "Pick a date and get a QR code for your bag." },
        { title: "My pickups", description: "Track each bag from collection to the warehouse." },
        { title: "Waste insights", description: "See what your household throws away, by category." },
      ]}
    />
  );
}
