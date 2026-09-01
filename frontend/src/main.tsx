import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App'
import { ActorProvider, ToastProvider } from './hooks'
import { SessionProvider } from './hooks/useSession'
import { ThemeProvider } from './hooks/useTheme'
import { I18nProvider } from './i18n/I18nProvider'
import './index.css'

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <ThemeProvider>
      <I18nProvider>
        <BrowserRouter>
          <ToastProvider>
            <SessionProvider>
            <ActorProvider>
              <App />
            </ActorProvider>
            </SessionProvider>
          </ToastProvider>
        </BrowserRouter>
      </I18nProvider>
    </ThemeProvider>
  </React.StrictMode>,
)
