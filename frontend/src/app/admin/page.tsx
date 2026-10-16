import DashboardPage from "@/components/dashboard/DashboardPage";

export default function AdminDashboard() {
  return (
    <DashboardPage
      role="admin"
      comingSoon={[
        { title: "Users & roles", description: "Create collector and operator accounts." },
        { title: "Zones & collectors", description: "Assign collectors to service zones." },
        { title: "Platform stats", description: "Pickups, bags and classification trends." },
      ]}
    />
  );
}
