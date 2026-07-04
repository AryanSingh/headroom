import { RootProvider } from 'fumadocs-ui/provider/next';
import './global.css';
import { Inter } from 'next/font/google';
import type { Metadata } from 'next';

const inter = Inter({
  subsets: ['latin'],
});

// Canonical URL for the live docs. ``metadataBase`` resolves the og:url
// and twitter:url for every page; pointing it at the actual live site
// is what lets crawlers (search + LLM) follow the right canonical and
// pick up ``/llms.txt`` / ``/sitemap.xml`` / og images. Override at
// build time via ``NEXT_PUBLIC_SITE_URL`` (e.g. when promoting to a
// custom domain).
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? 'https://cutctx.com';

export const metadata: Metadata = {
  title: {
 default: 'Cutctx — Context Control Plane for AI Agents',
 template: '%s | Cutctx',
  },
  description:
    'Local-first context control plane for AI agents. Govern what reaches the model, attribute spend and savings, remember shared context, and compress noisy tool output when it helps.',
  metadataBase: new URL(SITE_URL),
  alternates: {
    canonical: '/',
  },
  openGraph: {
    type: 'website',
    siteName: 'Cutctx',
    title: 'Cutctx — Context Control Plane for AI Agents',
    description:
      'Local-first context control plane for AI agents: govern, attribute, remember, and compress without a SaaS hop.',
    url: '/',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Cutctx — Context Control Plane for AI Agents',
    description:
      'Local-first context control plane for AI agents: govern, attribute, remember, and compress without a SaaS hop.',
  },
};

export default function Layout({ children }: LayoutProps<'/'>) {
  return (
    <html lang="en" className={inter.className} suppressHydrationWarning>
      <body className="flex flex-col min-h-screen">
        <RootProvider>{children}</RootProvider>
      </body>
    </html>
  );
}
