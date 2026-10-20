import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "@fontsource/schibsted-grotesk/500.css";
import "@fontsource/schibsted-grotesk/600.css";
import "@fontsource/schibsted-grotesk/700.css";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./globals.css";
import { Providers } from "@/components/providers/providers";
import { MobileNav, Sidebar } from "@/components/shell/sidebar";

export const metadata: Metadata = {
  title: { default: "AeroPredict — Aircraft Predictive Maintenance", template: "%s · AeroPredict" },
  description: "Research prototype for predictive maintenance across five aircraft subsystems: engine, battery, hydraulic, fuel and landing gear.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#000000" },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="bg-canvas text-foreground antialiased">
        <Providers>
          <div className="flex min-h-screen items-start">
            <Sidebar />
            <main className="h-screen min-w-0 flex-1 overflow-y-auto">
              <MobileNav />
              {children}
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
