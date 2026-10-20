"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";

/** Re-mounts on every navigation, so each page fades up into place. */
export default function Template({ children }: { children: ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.28, ease: [0.22, 0.61, 0.36, 1] }}>
      {children}
    </motion.div>
  );
}
