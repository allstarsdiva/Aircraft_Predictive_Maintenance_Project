"use client";

import type { ReactNode } from "react";
import { ChakraProvider } from "@chakra-ui/react";
import { MotionConfig } from "framer-motion";
import { ThemeProvider } from "next-themes";
import { TooltipProvider } from "@/components/ui/tooltip";
import { FleetProvider } from "@/lib/fleet/fleet-provider";
import { system } from "./chakra-system";
import { EmotionRegistry } from "./emotion-registry";

/** Every client-side provider, mounted once at the root layout. */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <EmotionRegistry>
        <ChakraProvider value={system}>
          <MotionConfig reducedMotion="user">
            <TooltipProvider delayDuration={200}>
              <FleetProvider>{children}</FleetProvider>
            </TooltipProvider>
          </MotionConfig>
        </ChakraProvider>
      </EmotionRegistry>
    </ThemeProvider>
  );
}
