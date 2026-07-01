import { Component } from "react"

interface Props { children: React.ReactNode }
interface State { hasError: boolean; error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, background: "#08080e", color: "#fff", minHeight: "100vh", fontFamily: "sans-serif" }}>
          <h1 style={{ fontSize: 18, marginBottom: 12 }}>Something went wrong</h1>
          <pre style={{ color: "#ff6b6b", fontSize: 13, whiteSpace: "pre-wrap" }}>
            {this.state.error?.toString()}
          </pre>
          <pre style={{ color: "#888", fontSize: 11, marginTop: 16, whiteSpace: "pre-wrap" }}>
            {this.state.error?.stack}
          </pre>
        </div>
      )
    }
    return this.props.children
  }
}
