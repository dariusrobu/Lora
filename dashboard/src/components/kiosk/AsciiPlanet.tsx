import { useRef, useEffect } from "react"

const CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
const SPHERE_N = 320
const RING_N = 220
const R = 150
const RI = 190
const RO = 300
const GA = Math.PI * (3 - Math.sqrt(5))
const TILT = 18 * Math.PI / 180
const CT = Math.cos(TILT)
const ST = Math.sin(TILT)

interface Pt { x: number; y: number; z: number; c: string }

function sphere(n: number, r: number): Pt[] {
  const a: Pt[] = []
  for (let i = 0; i < n; i++) {
    const θ = GA * i
    const φ = Math.acos(1 - 2 * (i + 0.5) / n)
    a.push({
      x: r * Math.sin(φ) * Math.cos(θ),
      y: r * Math.cos(φ),
      z: r * Math.sin(φ) * Math.sin(θ),
      c: CHARS[Math.floor(Math.random() * CHARS.length)],
    })
  }
  return a
}

function ring(n: number, r1: number, r2: number): Pt[] {
  const a: Pt[] = []
  for (let i = 0; i < n; i++) {
    const θ = Math.random() * 2 * Math.PI
    const r = r1 + Math.random() * (r2 - r1)
    a.push({
      x: r * Math.cos(θ),
      y: (Math.random() - 0.5) * 12,
      z: r * Math.sin(θ),
      c: CHARS[Math.floor(Math.random() * CHARS.length)],
    })
  }
  return a
}

export default function AsciiPlanet() {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const cvs = ref.current
    if (!cvs) return
    const ctx = cvs.getContext("2d")
    if (!ctx) return

    const pts = [...sphere(SPHERE_N, R), ...ring(RING_N, RI, RO)]
    let rot = 0
    let id = 0

    function draw() {
      const w = cvs.clientWidth
      const h = cvs.clientHeight
      if (!w || !h) { id = requestAnimationFrame(draw); return }
      const dpr = window.devicePixelRatio || 1
      cvs.width = w * dpr
      cvs.height = h * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

      rot += 0.005
      const cr = Math.cos(rot)
      const sr = Math.sin(rot)

      const t = pts.map(p => {
        const rx = p.x * cr + p.z * sr
        const rz = -p.x * sr + p.z * cr
        const ty = p.y * CT - rz * ST
        const tz = p.y * ST + rz * CT
        return { x: rx, y: ty, z: tz, c: p.c }
      })

      t.sort((a, b) => a.z - b.z)

      const f = 500
      const cx = w / 2
      const cy = h / 2
      const maxZ = R * 1.5

      ctx.clearRect(0, 0, w, h)
      ctx.font = "14px monospace"
      ctx.textAlign = "center"
      ctx.textBaseline = "middle"

      for (const p of t) {
        const s = f / (f + p.z + R)
        const sx = cx + p.x * s
        const sy = cy + p.y * s
        if (sx < -20 || sx > w + 20 || sy < -20 || sy > h + 20) continue
        const a = 0.08 + (p.z + maxZ) / (2 * maxZ) * 0.7
        ctx.fillStyle = `rgba(255,255,255,${a.toFixed(3)})`
        ctx.fillText(p.c, sx, sy)
      }

      id = requestAnimationFrame(draw)
    }

    id = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(id)
  }, [])

  return <canvas ref={ref} className="w-full h-full block" />
}
