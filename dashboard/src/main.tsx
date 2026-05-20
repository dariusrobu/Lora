import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import BoardApp from './BoardApp.tsx'

const isBoard = window.location.pathname.includes('/board') ||
  window.location.search.includes('board=1');

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isBoard ? <BoardApp /> : <App />}
  </StrictMode>,
)

