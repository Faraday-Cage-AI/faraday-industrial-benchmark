import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  metadataBase: new URL('https://faraday-industrial-benchmark.faraday-2894.chatgpt.site'),
  title: {
    default: 'Faraday Industrial Benchmark',
    template: '%s · Faraday Industrial Benchmark',
  },
  description:
    'A dynamic executable benchmark for AI agents across ERP, SCM, MES, manufacturing, distribution, and the industrial back office.',
  keywords: [
    'AI agent benchmark',
    'industrial AI',
    'ERP benchmark',
    'supply chain benchmark',
    'manufacturing AI',
    'MES',
  ],
  openGraph: {
    type: 'website',
    url: '/',
    title: 'Faraday Industrial Benchmark',
    description:
      'Can your agent run the industrial enterprise? 62 executable episodes across manufacturing, supply chain, distribution, and the back office.',
  },
  twitter: {
    card: 'summary',
    title: 'Faraday Industrial Benchmark',
    description:
      'A dynamic executable benchmark for AI agents across the industrial enterprise.',
  },
  alternates: { canonical: '/' },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
