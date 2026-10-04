"use client"

import { useEffect, useRef } from "react"

// Keeps a scroll container pinned to the bottom when new items arrive,
// unless the user has scrolled up to read older items.
export function useStickToBottom<T extends HTMLElement>(count: number) {
  const ref = useRef<T>(null)
  const pinned = useRef(true)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const onScroll = () => {
      pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48
    }
    el.addEventListener("scroll", onScroll)
    return () => el.removeEventListener("scroll", onScroll)
  }, [])

  useEffect(() => {
    const el = ref.current
    if (el && pinned.current) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" })
  }, [count])

  return ref
}
