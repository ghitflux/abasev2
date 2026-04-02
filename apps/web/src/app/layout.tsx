import type { Metadata } from "next";
import localFont from "next/font/local";

import { AppProviders } from "@/providers/app-providers";
import "./globals.css";

const inter = localFont({
  src: "../assets/fonts/InterVariable.woff2",
  variable: "--font-sans",
  display: "swap",
  weight: "100 900",
});

const plexMono = localFont({
  src: [
    {
      path: "../assets/fonts/IBMPlexMono-Regular.ttf",
      weight: "400",
      style: "normal",
    },
    {
      path: "../assets/fonts/IBMPlexMono-Medium.ttf",
      weight: "500",
      style: "normal",
    },
  ],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ABASE",
  description: "Gestão de associados da ABASE Piauí.",
  icons: {
    icon: [
      { url: "/favicon.ico?v=2" },
      { url: "/ABASE.png", type: "image/png" },
    ],
    shortcut: "/favicon.ico?v=2",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" className="dark" suppressHydrationWarning>
      <body className={`${inter.variable} ${plexMono.variable} min-h-screen bg-background font-sans text-foreground antialiased`}>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
