import { animate } from "framer-motion"
import { useEffect, useRef } from "react"

interface Props {
  value: number
  decimals?: number
  prefix?: string
  suffix?: string
}

export default function AnimatedNumber({ value, decimals = 0, prefix = "", suffix = "" }: Props) {
  const ref = useRef<HTMLSpanElement>(null)
  const prevRef = useRef(value)

  useEffect(() => {
    const node = ref.current
    if (!node) return
    const prev = prevRef.current
    if (prev === value) return
    const controls = animate(prev, value, {
      duration: 0.6,
      ease: [0.32, 0.72, 0, 1],
      onUpdate: (v) => { node.textContent = prefix + Number(v.toFixed(decimals)).toLocaleString() + suffix },
    })
    prevRef.current = value
    return () => controls.stop()
  }, [value, decimals, prefix, suffix])

  return <span ref={ref}>{prefix}{Number(value.toFixed(decimals)).toLocaleString()}{suffix}</span>
}
