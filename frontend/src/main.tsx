import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

// No StrictMode: Cesium Viewer does not love double-mount in dev.
createRoot(document.getElementById("root")!).render(<App />);
