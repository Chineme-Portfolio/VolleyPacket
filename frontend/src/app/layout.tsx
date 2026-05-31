import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import AppShell from "@/components/AppShell";
import { ToastProvider } from "@/components/Toast";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const SITE_URL = "https://volleypacket.com";

export const metadata: Metadata = {
  title: {
    default: "VolleyPacket — Send Batch Emails & Personalized PDFs from a Spreadsheet",
    template: "%s | VolleyPacket",
  },
  description:
    "Upload a spreadsheet, generate personalized PDFs with AI, and send thousands of batch emails in one click. Supports Resend, SendGrid, Gmail SMTP, and more.",
  keywords: [
    "batch email sender",
    "send bulk emails from spreadsheet",
    "personalized PDF generator",
    "mail merge tool",
    "bulk email tool",
    "batch SMS sender",
    "email merge from Excel",
    "AI template generator",
    "VolleyPacket",
  ],
  authors: [{ name: "VolleyPacket" }],
  creator: "VolleyPacket",
  metadataBase: new URL(SITE_URL),
  alternates: {
    canonical: "/",
  },
  icons: {
    icon: "/favicon.png",
    apple: "/favicon.png",
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: SITE_URL,
    siteName: "VolleyPacket",
    title: "VolleyPacket — Send Batch Emails & Personalized PDFs from a Spreadsheet",
    description:
      "Upload a spreadsheet, generate personalized PDFs with AI, and send thousands of batch emails in one click.",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "VolleyPacket — Batch emails, made simple",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "VolleyPacket — Batch Emails & Personalized PDFs",
    description:
      "Upload a spreadsheet, generate personalized PDFs with AI, and send thousands of batch emails in one click.",
    images: ["/og-image.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
};

// JSON-LD structured data for Google rich results
const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      name: "VolleyPacket",
      url: SITE_URL,
      logo: `${SITE_URL}/logo-full.png`,
      description:
        "Batch email and personalized PDF generation platform. Upload a spreadsheet, design templates with AI, send thousands in one click.",
    },
    {
      "@type": "SoftwareApplication",
      name: "VolleyPacket",
      url: SITE_URL,
      applicationCategory: "BusinessApplication",
      operatingSystem: "Web",
      description:
        "Upload a spreadsheet, generate personalized PDFs with AI, and send batch emails, SMS, and more. Supports multiple email providers.",
      offers: {
        "@type": "AggregateOffer",
        lowPrice: "0",
        highPrice: "49.99",
        priceCurrency: "USD",
        offerCount: "3",
      },
      featureList: [
        "AI-powered PDF template generation",
        "Batch email sending from spreadsheet",
        "Batch SMS dispatch",
        "Photo downloads",
        "Smart email typo correction",
        "Real-time progress tracking",
        "Delivery reports",
        "Multiple email provider support (Resend, SendGrid, Gmail, Outlook, Zoho, Custom SMTP)",
      ],
    },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full`}>
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body className="min-h-full font-[family-name:var(--font-inter)]">
        <AuthProvider>
          <ToastProvider>
            <AppShell>{children}</AppShell>
          </ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
