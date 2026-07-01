import { Component } from "react"

interface Props { children: React.ReactNode }
interface State { hasError: boolean }

const RESET_AFTER_MS = 30_000

export class WidgetErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }
  private timer: ReturnType<typeof setTimeout> | null = null

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[WidgetError]", error, info.componentStack)
  }

  componentDidUpdate(_prevProps: Props, prevState: State) {
    if (this.state.hasError && !prevState.hasError) {
      this.timer = setTimeout(() => this.setState({ hasError: false }), RESET_AFTER_MS)
    }
  }

  componentWillUnmount() {
    if (this.timer) clearTimeout(this.timer)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center h-full text-white/20 text-xs">
          Widget error
        </div>
      )
    }
    return this.props.children
  }
}
