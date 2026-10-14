import React from "react"
import { createRoot } from "react-dom/client"
import App from "./App"
import { telegram } from "./api"
import "./style.css"

telegram?.ready?.()
telegram?.expand?.()

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>)
