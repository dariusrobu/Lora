import { Component } from "react"

interface Props { children: React.ReactNode }
interface State { hasError: boolean; error: Error | null; copied: boolean }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null, copied: false }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: any) {
    try {
      fetch("/api/client-error", {
        method: "POST",
        headers: { "Content-Type": "application/json", "ngrok-skip-browser-warning": "true" },
        body: JSON.stringify({
          error: error.toString(),
          stack: error.stack || errorInfo?.componentStack,
          userAgent: navigator.userAgent,
        }),
      }).catch(() => {})
    } catch {}
  }

  handleCopy = () => {
    const text = `${this.state.error?.toString()}\n\n${this.state.error?.stack}`
    navigator.clipboard?.writeText(text).then(() => {
      this.setState({ copied: true })
      setTimeout(() => this.setState({ copied: false }), 2000)
    })
  }

  handleReset = () => {
    localStorage.removeItem("lora_token")
    sessionStorage.clear()
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 24, background: "#0b0c10", color: "#fff", minHeight: "100vh", fontFamily: "-apple-system, BlinkMacSystemFont, sans-serif" }}>
          <div style={{ maxWidth: 600, margin: "0 auto", paddingTop: 40 }}>
            <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8, color: "#ff4d4f" }}>⚠️ Application Error</h1>
            <p style={{ fontSize: 13, color: "#8c8c8c", marginBottom: 20 }}>
              An error occurred while rendering the page on this device.
            </p>
            <pre style={{ color: "#ff7875", background: "#1f1f1f", padding: 14, borderRadius: 10, fontSize: 12, whiteSpace: "pre-wrap", overflowX: "auto", border: "1px solid #303030", maxHeight: 250 }}>
              {this.state.error?.toString()}
            </pre>
            <div style={{ display: "flex", gap: 10, marginTop: 20, flexWrap: "wrap" }}>
              <button
                onClick={this.handleCopy}
                style={{ padding: "10px 16px", background: "#303030", color: "#fff", border: "none", borderRadius: 8, fontSize: 13, cursor: "pointer", fontWeight: 600 }}
              >
                {this.state.copied ? "✓ Copied!" : "📋 Copy Error"}
              </button>
              <button
                onClick={this.handleReset}
                style={{ padding: "10px 16px", background: "#7c3aed", color: "#fff", border: "none", borderRadius: 8, fontSize: 13, cursor: "pointer", fontWeight: 600 }}
              >
                🔄 Reset & Reload
              </button>
            </div>
            {this.state.error?.stack && (
              <pre style={{ color: "#595959", fontSize: 10, marginTop: 20, whiteSpace: "pre-wrap", maxHeight: 150, overflowY: "auto" }}>
                {this.state.error.stack}
              </pre>
            )}
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
