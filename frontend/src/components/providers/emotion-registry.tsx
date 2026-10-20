"use client";

import { useState, type ReactNode } from "react";
import { useServerInsertedHTML } from "next/navigation";
import createCache, { type EmotionCache } from "@emotion/cache";
import { CacheProvider } from "@emotion/react";

/**
 * Collects the styles Emotion (Chakra UI's styling engine) generates during a
 * server render and emits them into <head> via useServerInsertedHTML.
 *
 * Without this, Emotion writes <style> tags inline in <body>, which the
 * browser render does not produce, and React reports a hydration mismatch.
 */
export function EmotionRegistry({ children }: { children: ReactNode }) {
  const [{ cache, flush }] = useState(() => {
    const cache: EmotionCache = createCache({ key: "ck" });
    // compat: route Global styles through cache.insert instead of inline tags.
    cache.compat = true;
    const insert = cache.insert;
    let inserted: string[] = [];
    cache.insert = (...args: Parameters<EmotionCache["insert"]>) => {
      const serialized = args[1];
      if (cache.inserted[serialized.name] === undefined) inserted.push(serialized.name);
      return insert(...args);
    };
    const flush = () => {
      const names = inserted;
      inserted = [];
      return names;
    };
    return { cache, flush };
  });

  useServerInsertedHTML(() => {
    const names = flush();
    if (names.length === 0) return null;
    let styles = "";
    for (const name of names) {
      const css = cache.inserted[name];
      if (typeof css === "string") styles += css;
    }
    return <style key={cache.key} data-emotion={`${cache.key} ${names.join(" ")}`} dangerouslySetInnerHTML={{ __html: styles }} />;
  });

  return <CacheProvider value={cache}>{children}</CacheProvider>;
}
