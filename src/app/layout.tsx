
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GeoNOVA | Earth Intelligence",
  description:
    "An AI-powered Earth intelligence and scientific discovery platform.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
