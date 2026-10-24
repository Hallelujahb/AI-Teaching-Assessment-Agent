import React from 'react'
import ReactDOM from 'react-dom/client'
import Login from './pages/Login'
import { applyTheme, initialTheme } from './theme'

applyTheme(initialTheme())
ReactDOM.createRoot(document.getElementById('root')).render(<Login />)
