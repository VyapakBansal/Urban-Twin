import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { error: string | null; resetKey: number };

/** Keeps chrome visible if Cesium throws (WebGL / entity errors). */
export class MapErrorBoundary extends Component<Props, State> {
  state: State = { error: null, resetKey: 0 };

  static getDerivedStateFromError(err: Error): Partial<State> {
    return { error: err.message || "Map failed to render" };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[urban-twin] map error", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="map-fallback map-error" role="alert">
          <p>Map failed to load</p>
          <p className="muted">{this.state.error}</p>
          <button
            type="button"
            onClick={() =>
              this.setState((s) => ({
                error: null,
                resetKey: s.resetKey + 1,
              }))
            }
          >
            Retry
          </button>
        </div>
      );
    }
    return (
      <div className="map-root" key={this.state.resetKey}>
        {this.props.children}
      </div>
    );
  }
}
