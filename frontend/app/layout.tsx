import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {title: 'Adscope · Meta Ads Analytics', description: 'แดชบอร์ดวิเคราะห์โฆษณา · CSV-only · Read-only'};
export default function RootLayout({children}:{children:React.ReactNode}) {
  return <html lang="th"><body>{children}</body></html>;
}
