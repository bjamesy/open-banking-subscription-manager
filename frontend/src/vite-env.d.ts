/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_GOOGLE_CLIENT_ID?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// Minimal ambient type for the one Google Identity Services surface this app
// uses (loaded via the <script> tag in index.html, not an npm package).
interface GoogleCredentialResponse {
  credential: string
}

interface Window {
  google?: {
    accounts: {
      id: {
        initialize(config: {
          client_id: string
          callback: (response: GoogleCredentialResponse) => void
        }): void
        renderButton(
          parent: HTMLElement,
          options: {
            theme?: 'outline' | 'filled_blue' | 'filled_black'
            size?: 'small' | 'medium' | 'large'
            shape?: 'rectangular' | 'pill' | 'circle' | 'square'
            text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin'
            width?: number
          },
        ): void
      }
    }
  }
}
