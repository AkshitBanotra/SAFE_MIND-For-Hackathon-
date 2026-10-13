import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'SAFE-MIND — A private space to talk',
  description: 'A local-first, privacy-focused conversational companion.',
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>
}
