import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Elite Reasoning Telemetry",
  description: "Local-first telemetry dashboard for Elite Reasoning MCP memory, goals, decisions, and workflow signals.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
