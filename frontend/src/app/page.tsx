import type { Metadata } from "next";

import Landing from "@/components/landing/Landing";

const TITLE = "EcoTrace: know what every household throws away";
const DESCRIPTION =
  "QR-coded bags, phone scanning and Gemini turn household waste into data that helps people recycle more. Try the live demo in one click.";

export const metadata: Metadata = {
  metadataBase: new URL("https://ecotrace-9e406.web.app"),
  title: TITLE,
  description: DESCRIPTION,
  openGraph: {
    type: "website",
    url: "/",
    siteName: "EcoTrace",
    title: TITLE,
    description: DESCRIPTION,
    images: [{ url: "/landing/og-image.jpg", width: 1200, height: 630, alt: "Gemini listing the items in a waste bag" }],
  },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION, images: ["/landing/og-image.jpg"] },
};

/** Public landing page (static). */
export default function Home() {
  return <Landing />;
}
