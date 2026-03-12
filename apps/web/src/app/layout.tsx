import type { Metadata } from "next";
import { IBM_Plex_Mono, Sora } from "next/font/google";

import { AppProviders } from "@/providers/app-providers";
import "./globals.css";

const sora = Sora({
  variable: "--font-sans",
  subsets: ["latin"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "ABASE v2",
  description: "Gestão de associados da ABASE Piauí.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" className="dark" suppressHydrationWarning>
      <body className={`${sora.variable} ${plexMono.variable} min-h-screen bg-background font-sans text-foreground antialiased`}>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
