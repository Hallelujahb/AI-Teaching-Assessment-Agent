import React from 'react'
import ReactDOM from 'react-dom/client'
import { applyTheme, initialTheme } from './theme'

const KEY = 'qeleme_token'
const signedIn = () => !!localStorage.getItem(KEY)

applyTheme(initialTheme())

if (signedIn()) {
  import('./main.app.jsx')
} else {
  import('./pages/Login').then(({ default: Login }) => {
    ReactDOM.createRoot(document.getElementById('root')).render(
      <Login onLogin={() => window.location.reload()} />
    )
  })
}
