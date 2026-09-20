/**
 * useLoraLive — WebSocket hook for real-time Lora intent events.
 *
 * Connects to /ws/live and calls onEvent when the bot executes an intent
 * (task added, finance logged, etc.). Automatically reconnects on disconnect.
 *
 * Usage:
 *   useLoraLive((event) => {
 *     if (event.type === "intent_executed") {
 *       queryClient.invalidateQueries({ queryKey: ["tasks"] })
 *     }
 *   })
 */
import { useEffect, useRef, useCallback } from "react"

export interface LoraLiveEvent {
  type: "intent_executed" | "heartbeat"
  payload?: {
    module: string
    intent: string
    item_id?: number | null
  }
}

type EventHandler = (event: LoraLiveEvent) => void

const WS_URL = (() => {
  const base = import.meta.env.VITE_API_BASE_URL || ""
  if (base) {
    return base.replace(/^http/, "ws") + "/ws/live"
  }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:"
  return `${proto}//${window.location.host}/ws/live`
})()

export function useLoraLive(onEvent: EventHandler): void {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isMounted = useRef(true)
  const onEventRef = useRef<EventHandler>(onEvent)

  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  const connect = useCallback(() => {
    if (!isMounted.current) return
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return

    const token = localStorage.getItem("lora_token")
    if (!token) return

    // Browsers cannot attach Authorization to a WebSocket handshake. Put the
    // JWT in a WebSocket subprotocol header instead of the URL, where it could
    // leak into logs, browser history, and referrer headers.
    const ws = new WebSocket(WS_URL, ["lora-auth", token])
    wsRef.current = ws

    ws.onopen = () => {
      console.debug("[LoraLive] Connected to WebSocket")
    }

    ws.onmessage = (ev) => {
      try {
        const data: LoraLiveEvent = JSON.parse(ev.data)
        onEventRef.current(data)
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      console.debug("[LoraLive] Disconnected — reconnecting in 3s")
      if (isMounted.current) {
        reconnectTimer.current = setTimeout(connect, 3000)
      }
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [])

  useEffect(() => {
    isMounted.current = true
    connect()
    return () => {
      isMounted.current = false
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])
}
